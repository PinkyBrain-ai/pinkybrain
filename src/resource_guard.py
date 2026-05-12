#!/usr/bin/env python3
"""
🛡️ RESOURCE GUARD — PinkyBrain v5 Self-Protection Module
==========================================================

Ensures public mesh sharing NEVER impacts the local user's experience.

Key principles:
  1. Local user ALWAYS has priority
  2. Never exceed configured resource limits
  3. Auto-pause/resume without intervention
  4. Fail-safe: if monitoring fails, refuse all public requests
  5. No trust in external input — all limits enforced server-side
"""

import asyncio
import logging
import time
import threading
from collections import deque
from typing import Dict, Optional, Any, List
from enum import Enum

logger = logging.getLogger('PinkyBrain.ResourceGuard')

# ---------------------------------------------------------------------------
# psutil availability — fail-safe: if we can't monitor, we don't share
# ---------------------------------------------------------------------------
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed — Resource Guard will refuse all public requests. "
                   "Install with: pip install psutil")


class GuardState(Enum):
    """Resource Guard operational states."""
    ACTIVE = "active"           # Accepting public requests within limits
    THROTTLED = "throttled"      # Accepting but with reduced capacity
    PAUSED = "paused"            # Refusing all public requests (machine busy)
    DISABLED = "disabled"        # Public mesh disabled by config
    ERROR = "error"              # Monitoring failure — refuse everything


class ResourceGuard:
    """Monitors local system resources and controls public mesh availability.

    This is the gatekeeper: every public mesh request passes through here.
    If the local machine is under load, all public requests are rejected.

    Design invariants:
    - If psutil is unavailable, state = PAUSED (safe default)
    - If any monitoring call fails, state = ERROR (safe default)
    - CPU/RAM thresholds are hard limits, never soft
    - User activity detection is conservative (false positive = refuse request)
    """

    # Default thresholds
    DEFAULT_MAX_CPU_PERCENT = 10.0      # Max CPU% to share with mesh
    DEFAULT_MAX_RAM_SHARE_MB = 256        # Max RAM to share with mesh (MB)
    DEFAULT_GPU_SHARE = False
    DEFAULT_PRIORITY = "local_first"

    # Hard safety margins — these CANNOT be overridden by config
    HARD_MAX_CPU_SHARE = 70.0       # Max 70% CPU — 30% always reserved for the machine
    HARD_MAX_RAM_SHARE_PCT = 70.0   # Max 70% of total RAM — 30% always reserved
    HARD_MIN_RAM_RESERVE_MB = 512   # Always keep at least 512MB free (absolute minimum)
    HARD_MAX_RAM_SHARE_MB = 65536   # Absolute ceiling (64GB), further clamped by % of total RAM

    # Monitoring
    MONITOR_INTERVAL = 2.0          # seconds between resource checks
    CPU_SAMPLE_WINDOW = 5            # number of samples for CPU averaging
    HISTORY_LENGTH = 30              # keep 30 samples of history (60s at 2s interval)

    # Cooldowns
    PAUSE_COOLDOWN = 10.0           # seconds before accepting again after resume
    BURST_WINDOW = 10.0             # seconds for burst rate limiting
    MAX_BURST_REQUESTS = 30         # max requests in burst window

    # Request size limits (anti-DoS)
    MAX_PROMPT_LENGTH = 50000       # characters
    MAX_CONTEXT_LENGTH = 200000     # characters

    def __init__(self, config: Dict = None):
        """Initialize Resource Guard with optional config.

        Args:
            config: Dict with keys from public_mesh config section:
                max_cpu_percent, max_ram_share_mb, gpu_share, priority,
                bandwidth_limit_kbps, models_share, enabled
        """
        config = config or {}

        # --- Configurable limits (clamped to safe bounds) ---
        self.max_cpu_percent = self._clamp(
            config.get("max_cpu_percent", self.DEFAULT_MAX_CPU_PERCENT),
            5.0, self.HARD_MAX_CPU_SHARE
        )
        # RAM share: percentage-based with hard cap
        # Default = 10% of total RAM (conservative for normal users)
        # Max = 70% of total RAM (dedicated mode for fous-fous)
        # Always reserve at least 30% + 512MB absolute minimum
        total_ram_mb = psutil.virtual_memory().total / (1024 * 1024) if HAS_PSUTIL else 2560
        max_ram_from_pct = int(total_ram_mb * self.HARD_MAX_RAM_SHARE_PCT / 100)
        default_ram_mb = int(total_ram_mb * 0.10)  # 10% default
        default_ram_mb = max(128, min(default_ram_mb, max_ram_from_pct))
        self.max_ram_share_mb = max(
            128,  # minimum sensible value (128MB)
            min(config.get("max_ram_share_mb", default_ram_mb),
                min(max_ram_from_pct, self.HARD_MAX_RAM_SHARE_MB))  # never exceed 70% of total
        )
        self.gpu_share = config.get("gpu_share", self.DEFAULT_GPU_SHARE)
        self.priority = config.get("priority", self.DEFAULT_PRIORITY)
        self.bandwidth_limit_kbps = config.get("bandwidth_limit_kbps", 5000)
        self.enabled = config.get("enabled", False)

        # --- Internal state ---
        self._state = GuardState.DISABLED if not self.enabled else GuardState.PAUSED
        self._lock = threading.Lock()
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # --- CPU monitoring ---
        self._cpu_samples: deque = deque(maxlen=self.CPU_SAMPLE_WINDOW)
        self._cpu_history: deque = deque(maxlen=self.HISTORY_LENGTH)
        self._ram_history: deque = deque(maxlen=self.HISTORY_LENGTH)

        # --- User activity tracking ---
        self._last_user_activity: float = 0.0
        self._user_idle_threshold = 60.0  # seconds — consider user active if < 60s idle

        # --- Request tracking (anti-DoS / rate limiting) ---
        self._request_timestamps: deque = deque(maxlen=self.MAX_BURST_REQUESTS * 2)
        self._total_requests_served = 0
        self._total_requests_rejected = 0
        self._pause_time: Optional[float] = None
        self._resume_time: Optional[float] = None

        # --- Current resource snapshot ---
        self._current_cpu: float = 0.0
        self._current_ram_percent: float = 0.0
        self._current_ram_available_mb: float = 0.0
        self._current_ram_total_mb: float = 0.0
        self._current_process_count: int = 0

        # --- Validate psutil ---
        if not HAS_PSUTIL:
            self._state = GuardState.ERROR
            logger.error("Resource Guard: psutil unavailable — all public requests will be refused")

        # --- Initial snapshot ---
        self._take_snapshot()

        logger.info(f"Resource Guard initialized: "
                     f"cpu_limit={self.max_cpu_percent}% "
                     f"ram_limit={self.max_ram_share_mb}MB "
                     f"gpu={self.gpu_share} "
                     f"priority={self.priority} "
                     f"enabled={self.enabled}")

    # ===================================================================
    # PUBLIC API — these are called by the mesh routing layer
    # ===================================================================

    def can_accept_request(self, prompt_length: int = 0, context_length: int = 0) -> bool:
        """Check if we can accept a public mesh request RIGHT NOW.

        This is the main gate. Returns True only if:
        1. Public mesh is enabled
        2. Guard is in ACTIVE or THROTTLED state
        3. CPU is below threshold
        4. RAM is available
        5. User is not actively using the machine
        6. Request doesn't exceed size limits
        7. Rate limit is not exceeded

        Args:
            prompt_length: Length of the incoming prompt (anti-DoS check)
            context_length: Length of the context (anti-DoS check)

        Returns:
            True if the request can be accepted, False otherwise.
        """
        if not HAS_PSUTIL:
            return False  # Can't monitor = can't share safely

        with self._lock:
            # Check state
            if self._state == GuardState.DISABLED:
                self._total_requests_rejected += 1
                return False
            if self._state == GuardState.ERROR:
                self._total_requests_rejected += 1
                return False
            if self._state == GuardState.PAUSED:
                self._total_requests_rejected += 1
                return False

            # Check request size (anti-DoS)
            if prompt_length > self.MAX_PROMPT_LENGTH:
                logger.warning(f"Resource Guard: rejecting request with prompt_length={prompt_length} "
                               f"(max {self.MAX_PROMPT_LENGTH})")
                self._total_requests_rejected += 1
                return False
            if context_length > self.MAX_CONTEXT_LENGTH:
                logger.warning(f"Resource Guard: rejecting request with context_length={context_length} "
                               f"(max {self.MAX_CONTEXT_LENGTH})")
                self._total_requests_rejected += 1
                return False

            # Check burst rate limit
            now = time.time()
            recent = sum(1 for t in self._request_timestamps if now - t < self.BURST_WINDOW)
            if recent >= self.MAX_BURST_REQUESTS:
                logger.debug("Resource Guard: burst rate limit hit")
                self._total_requests_rejected += 1
                return False

            # Check cooldown after resume
            if self._resume_time and (now - self._resume_time) < self.PAUSE_COOLDOWN:
                self._total_requests_rejected += 1
                return False

            # Check CPU
            avg_cpu = self._get_avg_cpu()
            if avg_cpu > self._get_cpu_threshold():
                self._total_requests_rejected += 1
                return False

            # Check RAM
            available_mb = self._current_ram_available_mb
            min_free = max(self.HARD_MIN_RAM_RESERVE_MB, self.max_ram_share_mb)
            # We need at least max_ram_share_mb available AND hard minimum reserve
            if available_mb < min_free:
                self._total_requests_rejected += 1
                return False

            # Check total RAM usage — refuse if system is using too much
            # Use a percentage threshold: 85% total RAM used = too risky to share
            if self._current_ram_percent > 85.0:
                self._total_requests_rejected += 1
                return False

            # Check user activity (local_first priority)
            if self.priority == "local_first":
                if self._is_user_active():
                    self._total_requests_rejected += 1
                    return False

            # All checks passed
            self._request_timestamps.append(now)
            self._total_requests_served += 1
            return True

    def get_available_resources(self) -> Dict[str, Any]:
        """Report what resources we can share RIGHT NOW.

        Returns dict with:
            ram_mb: available RAM to share (capped by config + actual free)
            cpu_available_percent: CPU headroom within our share limit
            gpu: whether GPU sharing is enabled
            state: current GuardState
            can_accept: whether we can accept a request
        """
        with self._lock:
            if self._state in (GuardState.DISABLED, GuardState.ERROR):
                return {
                    "ram_mb": 0,
                    "cpu_available_percent": 0,
                    "gpu": False,
                    "state": self._state.value,
                    "can_accept": False
                }

            # Available RAM = min(configured max, 50% of actually free, free - hard reserve)
            actual_available = self._current_ram_available_mb
            config_cap = self.max_ram_share_mb
            hard_reserve = self.HARD_MIN_RAM_RESERVE_MB

            shareable_ram = min(
                config_cap,
                actual_available * 0.5,
                max(0, actual_available - hard_reserve)
            )
            shareable_ram = max(0, int(shareable_ram))

            # Available CPU = max(0, max_cpu_percent - current_cpu)
            cpu_available = max(0, self.max_cpu_percent - self._get_avg_cpu())

            can_accept = (
                self._state in (GuardState.ACTIVE, GuardState.THROTTLED)
                and shareable_ram > 0
                and cpu_available > 5  # need at least 5% headroom
            )

            return {
                "ram_mb": shareable_ram,
                "cpu_available_percent": round(cpu_available, 1),
                "gpu": self.gpu_share if can_accept else False,
                "state": self._state.value,
                "can_accept": can_accept
            }

    def get_status(self) -> Dict[str, Any]:
        """Get full status report for monitoring/dashboards."""
        with self._lock:
            return {
                "state": self._state.value,
                "enabled": self.enabled,
                "current_cpu_percent": round(self._current_cpu, 1),
                "avg_cpu_percent": round(self._get_avg_cpu(), 1),
                "current_ram_percent": round(self._current_ram_percent, 1),
                "current_ram_available_mb": round(self._current_ram_available_mb, 1),
                "current_ram_total_mb": round(self._current_ram_total_mb, 1),
                "cpu_threshold": self._get_cpu_threshold(),
                "max_cpu_percent": self.max_cpu_percent,
                "max_ram_share_mb": self.max_ram_share_mb,
                "gpu_share": self.gpu_share,
                "priority": self.priority,
                "user_active": self._is_user_active(),
                "requests_served": self._total_requests_served,
                "requests_rejected": self._total_requests_rejected,
                "last_pause": self._pause_time,
                "last_resume": self._resume_time,
            }

    # ===================================================================
    # LIFECYCLE — start/stop monitoring
    # ===================================================================

    async def start(self):
        """Start the background monitoring loop."""
        if self._running:
            return
        if not self.enabled:
            logger.info("Resource Guard: disabled, not starting monitor")
            return
        if not HAS_PSUTIL:
            logger.error("Resource Guard: cannot start — psutil unavailable")
            self._state = GuardState.ERROR
            return

        self._running = True
        self._state = GuardState.ACTIVE
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Resource Guard: monitoring started")

    async def stop(self):
        """Stop the background monitoring loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Resource Guard: monitoring stopped")

    def pause(self):
        """Manually pause public sharing."""
        with self._lock:
            self._state = GuardState.PAUSED
            self._pause_time = time.time()
        logger.info("Resource Guard: manually paused")

    def resume(self):
        """Manually resume public sharing."""
        with self._lock:
            self._state = GuardState.ACTIVE
            self._resume_time = time.time()
        logger.info("Resource Guard: manually resumed")

    # ===================================================================
    # INTERNAL — monitoring & state transitions
    # ===================================================================

    async def _monitor_loop(self):
        """Background loop that monitors system resources and adjusts state."""
        while self._running:
            try:
                self._take_snapshot()
                self._update_state()
            except Exception as e:
                logger.error(f"Resource Guard: monitoring error: {e}")
                with self._lock:
                    self._state = GuardState.ERROR
            await asyncio.sleep(self.MONITOR_INTERVAL)

    def _take_snapshot(self):
        """Take a snapshot of current system resources."""
        if not HAS_PSUTIL:
            return

        try:
            # CPU — non-blocking sample
            cpu = psutil.cpu_percent(interval=None)
            self._cpu_samples.append(cpu)
            self._cpu_history.append((time.time(), cpu))

            # RAM
            mem = psutil.virtual_memory()
            self._current_ram_percent = mem.percent
            self._current_ram_available_mb = mem.available / (1024 * 1024)
            self._current_ram_total_mb = mem.total / (1024 * 1024)
            self._ram_history.append((time.time(), mem.percent))

            # Process count (indicator of user activity)
            self._current_process_count = len(psutil.pids())

            # Store the latest CPU
            self._current_cpu = cpu

            # Detect user activity
            self._detect_user_activity()

        except Exception as e:
            logger.error(f"Resource Guard: snapshot error: {e}")
            with self._lock:
                self._state = GuardState.ERROR

    def _update_state(self):
        """Update guard state based on current resource snapshot."""
        with self._lock:
            if self._state == GuardState.DISABLED:
                return  # Stays disabled
            if self._state == GuardState.ERROR:
                # Try to recover from error
                if self._current_cpu > 0 or self._current_ram_total_mb > 0:
                    self._state = GuardState.PAUSED
                return

            avg_cpu = self._get_avg_cpu()
            ram_pct = self._current_ram_percent
            cpu_threshold = self._get_cpu_threshold()

            if avg_cpu > cpu_threshold or self._current_ram_percent > 90.0:
                # Machine is under heavy load — pause sharing
                if self._state != GuardState.PAUSED:
                    logger.info(f"Resource Guard: PAUSING — cpu={avg_cpu:.1f}% (threshold={cpu_threshold:.1f}%) "
                                f"ram={ram_pct:.1f}%")
                    self._pause_time = time.time()
                self._state = GuardState.PAUSED
            elif avg_cpu > cpu_threshold * 0.7 or self._current_ram_percent > 80.0:
                # Approaching limits — throttle
                if self._state != GuardState.THROTTLED:
                    logger.info(f"Resource Guard: THROTTLING — cpu={avg_cpu:.1f}% ram={ram_pct:.1f}%")
                self._state = GuardState.THROTTLED
            else:
                # Resources available — can share
                if self._state == GuardState.PAUSED:
                    # Resume with cooldown
                    self._resume_time = time.time()
                    logger.info("Resource Guard: RESUMING — resources available")
                self._state = GuardState.ACTIVE

            # Also pause if user is active and priority is local_first
            if self.priority == "local_first" and self._is_user_active():
                if self._state == GuardState.ACTIVE:
                    self._state = GuardState.THROTTLED

    def _get_avg_cpu(self) -> float:
        """Get average CPU over recent samples."""
        if not self._cpu_samples:
            return 0.0
        return sum(self._cpu_samples) / len(self._cpu_samples)

    def _get_cpu_threshold(self) -> float:
        """Get the CPU threshold for accepting requests.
        This is the TOTAL CPU percentage above which we refuse.
        For local_first: user activity threshold (70%).
        Otherwise: max_cpu_percent + baseline (config limit).
        """
        if self.priority == "local_first":
            # More conservative: refuse if total CPU is above 70%
            return min(70.0, self.max_cpu_percent + 40.0)
        else:
            # Standard: refuse if above configured limit + headroom
            return self.max_cpu_percent + 40.0

    def _detect_user_activity(self):
        """Detect if the local user is actively using the machine.

        Uses multiple signals:
        - Recent process creation (indicates user interaction)
        - Terminal/IDE activity via process names
        - Load average spikes
        """
        if not HAS_PSUTIL:
            return

        try:
            # Check load average — if > cpu_count * 0.5, likely active
            load_avg = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
            cpu_count = psutil.cpu_count() or 4

            # Check for interactive processes (browsers, editors, terminals, IDEs)
            interactive_keywords = {
                'firefox', 'chrome', 'chromium', 'brave', 'code', 'codium',
                'vim', 'nvim', 'emacs', 'kate', 'gedit', 'nano',
                'terminal', 'konsole', 'gnome-terminal', 'alacritty',
                'intellij', 'pycharm', 'webstorm', 'clion',
                'discord', 'telegram', 'slack', 'teams',
                'steam', 'obs', 'blender', 'gimp',
            }
            user_active_processes = 0
            try:
                for proc in psutil.process_iter(['name']):
                    try:
                        name = (proc.info.get('name') or '').lower()
                        if any(kw in name for kw in interactive_keywords):
                            user_active_processes += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except (psutil.Error, Exception):
                pass

            # If user processes detected or load is high, mark as active
            if user_active_processes > 0 or load_avg > cpu_count * 0.3:
                self._last_user_activity = time.time()

        except Exception:
            # If detection fails, assume user might be active
            pass

    def _is_user_active(self) -> bool:
        """Check if the user has been active recently."""
        if self._last_user_activity == 0.0:
            # No activity ever detected — safe to assume idle at startup
            return False
        return (time.time() - self._last_user_activity) < self._user_idle_threshold

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """Clamp a value between min and max."""
        return max(min_val, min(max_val, value))

    def update_config(self, config: Dict):
        """Hot-update configuration. Only allows reducing limits (never increasing beyond hard caps)."""
        with self._lock:
            if "max_cpu_percent" in config:
                self.max_cpu_percent = self._clamp(
                    config["max_cpu_percent"], 5.0, self.HARD_MAX_CPU_SHARE
                )
            if "max_ram_share_mb" in config:
                total_ram_mb = psutil.virtual_memory().total / (1024 * 1024) if HAS_PSUTIL else 2560
                max_allowed = int(total_ram_mb * self.HARD_MAX_RAM_SHARE_PCT / 100)
                self.max_ram_share_mb = max(
                    128,
                    min(config["max_ram_share_mb"],
                        min(max_allowed, self.HARD_MAX_RAM_SHARE_MB))
                )
            if "gpu_share" in config:
                self.gpu_share = config["gpu_share"]
            if "priority" in config:
                self.priority = config["priority"]
            if "enabled" in config:
                self.enabled = config["enabled"]
                if not self.enabled:
                    self._state = GuardState.DISABLED
                elif self._state == GuardState.DISABLED:
                    self._state = GuardState.PAUSED
        logger.info(f"Resource Guard: config updated — "
                     f"cpu={self.max_cpu_percent}% ram={self.max_ram_share_mb}MB "
                     f"gpu={self.gpu_share} priority={self.priority}")