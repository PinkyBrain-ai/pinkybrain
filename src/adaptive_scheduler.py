#!/usr/bin/env python3
"""
🧠 ADAPTIVE SCHEDULER — PinkyBrain v5
========================================

Decides resource management strategy automatically based on the number of
available peers. Transitions seamlessly between modes as the network grows
or shrinks.

Strategy tiers:
  1-3 peers   → "routing"          (whole models on one machine)
  4-10 peers  → "partial_sharding"  (models split into 2-4 chunks)
  11-50 peers → "full_sharding"     (pipeline parallel + 2x replication)
  51+ peers   → "raid_ram"          (distributed RAM + 3x replication + pre-fetch)

Design invariants:
  - Always have a fallback (sharding → routing)
  - Never exceed Resource Guard limits
  - Never leak private data to the public mesh
  - Validate all inputs (node data, chunk assignments, queries)
  - Rate-limit all mesh operations
  - Transition without service interruption
  - Redistribute chunks when peers join/leave
"""

import asyncio
import hashlib
import json
import logging
import time
import threading
from collections import deque
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field

logger = logging.getLogger('PinkyBrain.AdaptiveScheduler')

# ============================================================================
# CONSTANTS
# ============================================================================

# Strategy thresholds (peer counts)
ROUTING_MAX_PEERS = 3
PARTIAL_SHARDING_MAX_PEERS = 10
FULL_SHARDING_MAX_PEERS = 50

# Replication factors per strategy
REPLICATION_FACTOR = {
    "routing": 0,            # No replication — model runs on one node
    "partial_sharding": 2,   # 2 copies of each chunk
    "full_sharding": 2,      # 2 copies of each chunk
    "raid_ram": 3,           # 3 copies of each chunk
}

# Chunk sizes per strategy
CHUNK_COUNT = {
    "routing": 1,             # Whole model — no splitting
    "partial_sharding": 2,   # Split into 2-4 chunks
    "full_sharding": 4,      # Split into 4-8 chunks
    "raid_ram": 8,           # Split into 8+ chunks
}

# Safety limits
MAX_CHUNKS_PER_MODEL = 32          # Never split a model into more than 32 chunks
MAX_PEER_RAM_MB = 65536            # Cap on per-peer RAM claim (64 GB)
MIN_PEERS_FOR_SHARDING = 4         # Need at least 4 peers for sharding
MIN_PEERS_FOR_FULL_SHARDING = 11   # Need at least 11 for full sharding
MIN_PEERS_FOR_RAID = 51            # Need at least 51 for RAID RAM

# Transition timing
TRANSITION_QUIET_PERIOD = 5.0      # Seconds to wait before switching strategy
REDISTRIBUTION_COOLDOWN = 10.0     # Seconds between redistributions
MAX_TRANSITION_ATTEMPTS = 3        # Max attempts before fallback
HEALTH_CHECK_INTERVAL = 30.0       # Seconds between peer health checks
PEER_STALE_TIMEOUT = 300.0         # Seconds before a peer is considered stale

# Rate limiting
MAX_ROUTING_PER_SECOND = 10.0
MAX_SHARD_OPERATIONS_PER_SECOND = 5.0

# Input validation
MAX_MODEL_NAME_LENGTH = 128
MAX_NODE_ID_LENGTH = 256
MAX_PROMPT_LENGTH = 50000
MAX_CHUNK_DATA_SIZE = 64 * 1024 * 1024  # 64 MB per chunk transfer


# ============================================================================
# ENUMS
# ============================================================================

class Strategy(Enum):
    """Resource management strategies, ordered by minimum peer count."""
    ROUTING = "routing"
    PARTIAL_SHARDING = "partial_sharding"
    FULL_SHARDING = "full_sharding"
    RAID_RAM = "raid_ram"


class TransitionState(Enum):
    """States during a strategy transition."""
    STABLE = "stable"               # No transition in progress
    PREPARING = "preparing"          # Preparing new strategy (allocating chunks)
    TRANSITIONING = "transitioning"  # Switching over (brief window)
    FALLING_BACK = "falling_back"   # Fallback to simpler strategy after failure


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ChunkAssignment:
    """A model chunk assigned to a specific peer."""
    model: str
    chunk_index: int
    total_chunks: int
    peer_id: str
    peer_address: str
    size_mb: int
    is_replica: bool = False          # True if this is a replica (not primary)
    created_at: float = field(default_factory=time.time)
    last_verified: float = field(default_factory=time.time)
    verified: bool = False

    def to_dict(self) -> Dict:
        return {
            "model": self.model,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "peer_id": self.peer_id,
            "peer_address": self.peer_address,
            "size_mb": self.size_mb,
            "is_replica": self.is_replica,
            "created_at": self.created_at,
            "last_verified": self.last_verified,
            "verified": self.verified,
        }


@dataclass
class PeerInfo:
    """Information about a peer node for scheduling decisions."""
    node_id: str
    address: str
    name: str = ""
    ram_share_mb: int = 0
    cpu_cores: int = 0
    gpu_available: bool = False
    gpu_name: str = ""
    models: List[str] = field(default_factory=list)
    score: float = 0.0
    last_seen: float = 0.0
    uptime_seconds: int = 0
    bandwidth_kbps: int = 0

    @property
    def is_stale(self) -> bool:
        """Peer is stale if not seen recently."""
        return (time.time() - self.last_seen) > PEER_STALE_TIMEOUT

    @property
    def effective_ram(self) -> int:
        """Effective RAM available, capped at safety limit."""
        return min(max(0, self.ram_share_mb), MAX_PEER_RAM_MB)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "address": self.address,
            "name": self.name,
            "ram_share_mb": self.effective_ram,
            "cpu_cores": self.cpu_cores,
            "gpu_available": self.gpu_available,
            "gpu_name": self.gpu_name,
            "models": self.models,
            "score": self.score,
            "last_seen": self.last_seen,
            "uptime_seconds": self.uptime_seconds,
            "bandwidth_kbps": self.bandwidth_kbps,
        }


# ============================================================================
# INPUT VALIDATION
# ============================================================================

class InputValidator:
    """Validate all inputs entering the scheduler. Never trust external data."""

    @staticmethod
    def validate_model_name(name: str) -> bool:
        """Validate a model name."""
        if not isinstance(name, str):
            return False
        if len(name) == 0 or len(name) > MAX_MODEL_NAME_LENGTH:
            return False
        # Allow alphanumeric, hyphens, underscores, dots, colons (for tags)
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._:/")
        return all(c in allowed for c in name)

    @staticmethod
    def validate_node_id(node_id: str) -> bool:
        """Validate a node ID (Ed25519 hex key or similar)."""
        if not isinstance(node_id, str):
            return False
        if len(node_id) == 0 or len(node_id) > MAX_NODE_ID_LENGTH:
            return False
        # Allow alphanumeric, hyphens, underscores, dots
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        return all(c in allowed for c in node_id)

    @staticmethod
    def validate_address(address: str) -> bool:
        """Validate a network address (host:port)."""
        if not isinstance(address, str):
            return False
        if len(address) == 0 or len(address) > 512:
            return False
        # Basic check: no null bytes, no control chars
        if '\x00' in address or any(ord(c) < 32 for c in address):
            return False
        return True

    @staticmethod
    def validate_prompt(prompt: str) -> bool:
        """Validate a query prompt."""
        if not isinstance(prompt, str):
            return False
        return len(prompt) <= MAX_PROMPT_LENGTH

    @staticmethod
    def sanitize_peer_data(data: Dict) -> Optional[PeerInfo]:
        """Parse and validate peer data from tracker. Returns None if invalid."""
        if not isinstance(data, dict):
            return None

        node_id = data.get('node_id', '')
        address = data.get('address', '')

        if not InputValidator.validate_node_id(node_id):
            return None
        if not InputValidator.validate_address(address):
            return None

        # Validate and clamp numeric fields
        try:
            ram_share = int(data.get('ram_share_mb', 0) or 0)
            ram_share = max(0, min(ram_share, MAX_PEER_RAM_MB))
        except (ValueError, TypeError):
            ram_share = 0

        try:
            cpu_cores = int(data.get('cpu_cores', 0) or 0)
            cpu_cores = max(0, min(cpu_cores, 256))
        except (ValueError, TypeError):
            cpu_cores = 0

        try:
            score = float(data.get('score', 0) or 0)
            score = max(0.0, min(score, 1000.0))
        except (ValueError, TypeError):
            score = 0.0

        try:
            bandwidth = int(data.get('bandwidth_kbps', 0) or 0)
            bandwidth = max(0, min(bandwidth, 1_000_000))
        except (ValueError, TypeError):
            bandwidth = 0

        try:
            uptime = int(data.get('uptime_seconds', 0) or 0)
            uptime = max(0, min(uptime, 365 * 86400))
        except (ValueError, TypeError):
            uptime = 0

        # Validate models list
        raw_models = data.get('models', [])
        if not isinstance(raw_models, list):
            raw_models = []
        models = [m for m in raw_models if InputValidator.validate_model_name(str(m))]

        # Validate gpu
        gpu_available = bool(data.get('gpu_available', data.get('gpu', False)))
        gpu_name = str(data.get('gpu_name', ''))[:128] if data.get('gpu_name') else ''

        # Validate name
        name = str(data.get('name', ''))[:64]

        # Validate last_seen
        try:
            last_seen = float(data.get('last_seen', time.time()))
        except (ValueError, TypeError):
            last_seen = time.time()

        return PeerInfo(
            node_id=node_id,
            address=address,
            name=name,
            ram_share_mb=ram_share,
            cpu_cores=cpu_cores,
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            models=models,
            score=score,
            last_seen=last_seen,
            uptime_seconds=uptime,
            bandwidth_kbps=bandwidth,
        )


# ============================================================================
# RATE LIMITER
# ============================================================================

class SchedulerRateLimiter:
    """Token bucket rate limiter for scheduler operations."""

    def __init__(self, rate: float = 10.0, burst: int = 30):
        self.rate = rate
        self.burst = burst
        self._buckets: Dict[str, Dict] = {}
        self._lock = threading.RLock()

    def allow(self, key: str) -> bool:
        """Check if an operation is allowed under the rate limit."""
        with self._lock:
            now = time.time()
            bucket = self._buckets.get(key)
            if bucket is None:
                self._buckets[key] = {"tokens": float(self.burst), "last": now}
                bucket = self._buckets[key]

            elapsed = now - bucket["last"]
            bucket["tokens"] = min(self.burst, bucket["tokens"] + elapsed * self.rate)
            bucket["last"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return True
            return False

    def reset(self, key: str = None):
        """Reset rate limit for a key or all keys."""
        with self._lock:
            if key:
                self._buckets.pop(key, None)
            else:
                self._buckets.clear()


# ============================================================================
# MALICIOUS NODE DETECTOR
# ============================================================================

class MaliciousNodeDetector:
    """Track node behavior and flag potentially malicious nodes."""

    def __init__(self, max_failures: int = 5, max_false_claims: int = 3,
                 ban_duration: float = 3600.0):
        self.max_failures = max_failures
        self.max_false_claims = max_false_claims
        self.ban_duration = ban_duration

        self._failure_counts: Dict[str, int] = {}       # node_id -> failure count
        self._false_claims: Dict[str, int] = {}         # node_id -> false claim count
        self._banned: Dict[str, float] = {}              # node_id -> ban expiry time
        self._lock = threading.RLock()

    def record_failure(self, node_id: str):
        """Record a task failure on a node."""
        with self._lock:
            self._failure_counts[node_id] = self._failure_counts.get(node_id, 0) + 1
            if self._failure_counts[node_id] >= self.max_failures:
                self._ban(node_id)
                logger.warning(f"Node {node_id} banned: too many failures")

    def record_false_claim(self, node_id: str):
        """Record that a node claimed capabilities it doesn't have."""
        with self._lock:
            self._false_claims[node_id] = self._false_claims.get(node_id, 0) + 1
            if self._false_claims[node_id] >= self.max_false_claims:
                self._ban(node_id)
                logger.warning(f"Node {node_id} banned: false capability claims")

    def record_success(self, node_id: str):
        """Record a successful operation on a node, reducing failure count."""
        with self._lock:
            if node_id in self._failure_counts:
                self._failure_counts[node_id] = max(
                    0, self._failure_counts[node_id] - 1
                )

    def is_banned(self, node_id: str) -> bool:
        """Check if a node is currently banned."""
        with self._lock:
            expiry = self._banned.get(node_id)
            if expiry is None:
                return False
            if time.time() > expiry:
                # Ban expired
                del self._banned[node_id]
                return False
            return True

    def _ban(self, node_id: str):
        """Ban a node for the configured duration."""
        self._banned[node_id] = time.time() + self.ban_duration

    def get_banned_nodes(self) -> List[str]:
        """Get list of currently banned node IDs."""
        with self._lock:
            now = time.time()
            expired = [nid for nid, exp in self._banned.items() if now > exp]
            for nid in expired:
                del self._banned[nid]
            return list(self._banned.keys())

    def to_dict(self) -> Dict:
        with self._lock:
            return {
                "banned_nodes": len(self._banned),
                "failure_counts": dict(self._failure_counts),
                "false_claims": dict(self._false_claims),
            }


# ============================================================================
# ADAPTIVE SCHEDULER
# ============================================================================

class AdaptiveScheduler:
    """Decides resource strategy based on available peers.

    Integrates with:
      - TrackerClient: to discover available peers
      - ResourceGuard: to respect local resource limits
      - ModelNegotiator (optional): to factor in GPU/CPU capabilities

    Core principles:
      1. Automatically selects strategy based on peer count
      2. Transitions between strategies without interruption
      3. Falls back to simpler strategies on failure
      4. Redistributes chunks when peers join/leave
      5. Never exceeds Resource Guard limits
      6. Never leaks private data to the mesh
      7. Validates all inputs
      8. Rate-limits all mesh operations
    """

    def __init__(self, identity, resource_guard, tracker_client=None, config: Dict = None):
        """
        Args:
            identity: NodeIdentity instance for signing and identification
            resource_guard: ResourceGuard instance to respect local limits
            tracker_client: TrackerClient instance for peer discovery (optional)
            config: Scheduler-specific configuration
        """
        config = config or {}

        # Dependencies
        self.identity = identity
        self.resource_guard = resource_guard
        self.tracker_client = tracker_client

        # Current state
        self._strategy = Strategy.ROUTING
        self._transition_state = TransitionState.STABLE
        self._previous_strategy: Optional[Strategy] = None
        self._transition_start: float = 0.0

        # Chunk assignments: model -> {chunk_index -> [ChunkAssignment]}
        # Each chunk can have multiple assignments (replicas)
        self._chunk_assignments: Dict[str, Dict[int, List[ChunkAssignment]]] = {}

        # Known peers (from tracker + local discovery)
        self._peers: Dict[str, PeerInfo] = {}

        # Models we know about and their approximate sizes
        self._model_sizes: Dict[str, int] = config.get("model_sizes", {})

        # Strategy-specific config
        self._prefer_local = config.get("prefer_local", True)
        self._max_replication_override = config.get("max_replication", None)

        # Background tasks
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None

        # Timing
        self._last_strategy_update = 0.0
        self._last_redistribution = 0.0
        self._strategy_update_interval = config.get("strategy_update_interval", 60.0)
        self._redistribution_interval = config.get("redistribution_interval", 30.0)

        # Rate limiters
        self._routing_limiter = SchedulerRateLimiter(
            rate=MAX_ROUTING_PER_SECOND, burst=30
        )
        self._shard_limiter = SchedulerRateLimiter(
            rate=MAX_SHARD_OPERATIONS_PER_SECOND, burst=15
        )

        # Malicious node detector
        self._malicious_detector = MaliciousNodeDetector(
            max_failures=config.get("max_node_failures", 5),
            max_false_claims=config.get("max_false_claims", 3),
            ban_duration=config.get("ban_duration", 3600.0),
        )

        # Input validator
        self._validator = InputValidator()

        # Fallback tracking
        self._fallback_count = 0
        self._last_fallback_time = 0.0
        self._consecutive_failures = 0

        # Thread safety
        self._lock = threading.RLock()

        # Callbacks for extending behavior
        self._on_strategy_change = config.get("on_strategy_change", None)  # async callback
        self._on_redistribution = config.get("on_redistribution", None)    # async callback

        logger.info(f"AdaptiveScheduler initialized: strategy={self._strategy.value}")

    # ===================================================================
    # LIFECYCLE
    # ===================================================================

    async def start(self):
        """Start background monitoring and strategy updates."""
        if self._running:
            return
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info("AdaptiveScheduler: started")

    async def stop(self):
        """Stop background tasks."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
        logger.info("AdaptiveScheduler: stopped")

    # ===================================================================
    # STRATEGY SELECTION
    # ===================================================================

    def determine_strategy(self, peer_count: int) -> Strategy:
        """Determine the appropriate strategy based on peer count.

        This is a pure function — no side effects.

        Args:
            peer_count: Number of available (non-stale, non-banned) peers

        Returns:
            The appropriate Strategy for this peer count
        """
        if peer_count < MIN_PEERS_FOR_SHARDING:
            return Strategy.ROUTING
        elif peer_count <= PARTIAL_SHARDING_MAX_PEERS:
            return Strategy.PARTIAL_SHARDING
        elif peer_count <= FULL_SHARDING_MAX_PEERS:
            return Strategy.FULL_SHARDING
        else:
            return Strategy.RAID_RAM

    def get_replication_factor(self, strategy: Strategy = None) -> int:
        """Get replication factor for a strategy."""
        strategy = strategy or self._strategy
        factor = REPLICATION_FACTOR.get(strategy.value, 0)
        if self._max_replication_override is not None:
            factor = min(factor, self._max_replication_override)
        return factor

    def get_chunk_count(self, model: str, strategy: Strategy = None) -> int:
        """Calculate the number of chunks for a model given the strategy.

        Args:
            model: Model name (used to look up size)
            strategy: Strategy to use (defaults to current)

        Returns:
            Number of chunks to split the model into
        """
        strategy = strategy or self._strategy
        base_chunks = CHUNK_COUNT.get(strategy.value, 1)

        # If we know the model size, we can be more intelligent
        model_size_mb = self._model_sizes.get(model, 0)
        if model_size_mb > 0:
            # Don't create chunks smaller than 512 MB
            min_chunk_size_mb = 512
            max_chunks_by_size = max(1, model_size_mb // min_chunk_size_mb)
            # Don't create more chunks than peers (minus 1 for local)
            available_peers = len(self._get_eligible_peers())
            max_chunks_by_peers = max(1, available_peers)
            # Take the minimum of all constraints
            return min(base_chunks, max_chunks_by_size, max_chunks_by_peers, MAX_CHUNKS_PER_MODEL)

        return min(base_chunks, MAX_CHUNKS_PER_MODEL)

    # ===================================================================
    # STRATEGY UPDATE
    # ===================================================================

    async def update_strategy(self):
        """Called periodically or when peers change to update the strategy.

        This is the main decision loop. It:
          1. Fetches available peers from tracker
          2. Filters out stale and banned peers
          3. Determines the appropriate strategy
          4. Transitions to the new strategy if needed
          5. Redistributes chunks if needed
        """
        # Fetch peers from tracker
        available_peers = await self._fetch_available_peers()

        # Filter eligible peers
        eligible = self._get_eligible_peers()

        # Determine new strategy
        new_strategy = self.determine_strategy(len(eligible))

        # Check Resource Guard limits
        if not self._check_resource_guard():
            # Resource Guard says no — stay in routing (simplest)
            new_strategy = Strategy.ROUTING

        # Apply quiet period: don't change strategy too rapidly
        now = time.time()
        if (new_strategy != self._strategy
                and (now - self._last_strategy_update) < TRANSITION_QUIET_PERIOD):
            logger.debug(f"Strategy change to {new_strategy.value} deferred (quiet period)")
            return

        # Transition if strategy changed
        if new_strategy != self._strategy:
            success = await self._transition_to(new_strategy)
            if not success:
                # Fallback
                await self._fallback()
        else:
            # Same strategy — check if redistribution needed
            if (now - self._last_redistribution) > self._redistribution_interval:
                await self.redistribute_chunks()

        self._last_strategy_update = now

    # ===================================================================
    # STRATEGY TRANSITIONS
    # ===================================================================

    async def _transition_to(self, new_strategy: Strategy) -> bool:
        """Transition to a new strategy without interruption.

        Process:
          1. Mark as PREPARING
          2. Allocate chunks for the new strategy (in background)
          3. Once all chunks are allocated, mark as TRANSITIONING
          4. Switch to new strategy
          5. Mark as STABLE

        If preparation fails, fall back to a simpler strategy.

        Args:
            new_strategy: The target strategy

        Returns:
            True if transition succeeded, False if it failed (will fallback)
        """
        old_strategy = self._strategy

        logger.info(f"AdaptiveScheduler: transitioning from {old_strategy.value} "
                    f"to {new_strategy.value}")

        # Step 1: PREPARING — allocate chunks for new strategy
        self._transition_state = TransitionState.PREPARING
        self._transition_start = time.time()

        try:
            # Try to prepare the new chunk layout
            new_assignments = await self._prepare_chunk_assignments(new_strategy)

            if new_assignments is None:
                # Preparation failed — not enough peers/resources
                logger.warning(f"AdaptiveScheduler: failed to prepare chunks for "
                              f"{new_strategy.value}, falling back")
                self._transition_state = TransitionState.FALLING_BACK
                await self._fallback()
                return False

            # Step 2: TRANSITIONING — swap chunk assignments
            self._transition_state = TransitionState.TRANSITIONING
            with self._lock:
                self._previous_strategy = old_strategy
                self._chunk_assignments = new_assignments
                self._strategy = new_strategy

            # Step 3: STABLE
            self._transition_state = TransitionState.STABLE
            self._last_strategy_update = time.time()
            self._consecutive_failures = 0

            logger.info(f"AdaptiveScheduler: transitioned to {new_strategy.value}")

            # Notify callback
            if self._on_strategy_change:
                try:
                    await self._on_strategy_change(old_strategy.value, new_strategy.value)
                except Exception as e:
                    logger.error(f"Strategy change callback error: {e}")

            return True

        except Exception as e:
            logger.error(f"AdaptiveScheduler: transition error: {e}")
            self._transition_state = TransitionState.FALLING_BACK
            await self._fallback()
            return False

    async def _fallback(self):
        """Fall back to the simplest strategy (routing).

        Called when sharding or RAID fails. Guarantees the system
        remains functional even in degraded conditions.
        """
        self._fallback_count += 1
        self._last_fallback_time = time.time()
        self._consecutive_failures += 1

        logger.warning(f"AdaptiveScheduler: falling back to routing "
                       f"(fallback #{self._fallback_count}, "
                       f"consecutive failures: {self._consecutive_failures})")

        with self._lock:
            self._previous_strategy = self._strategy
            self._strategy = Strategy.ROUTING
            self._transition_state = TransitionState.STABLE
            # Clear chunk assignments — routing doesn't need them
            self._chunk_assignments = {}

        # Notify callback
        if self._on_strategy_change:
            try:
                previous = self._previous_strategy.value if self._previous_strategy else "unknown"
                await self._on_strategy_change(previous, Strategy.ROUTING.value)
            except Exception as e:
                logger.error(f"Strategy change callback error: {e}")

    # ===================================================================
    # CHUNK MANAGEMENT
    # ===================================================================

    async def _prepare_chunk_assignments(self, strategy: Strategy) -> Optional[Dict]:
        """Prepare chunk assignments for a strategy.

        Returns:
            Dict of model -> {chunk_index -> [ChunkAssignment]} or None on failure
        """
        if strategy == Strategy.ROUTING:
            # Routing: no chunks needed, models run on single nodes
            return {}

        eligible_peers = self._get_eligible_peers()
        if len(eligible_peers) < MIN_PEERS_FOR_SHARDING:
            logger.debug(f"Not enough eligible peers for sharding: {len(eligible_peers)}")
            return None

        replication = self.get_replication_factor(strategy)
        num_chunks = self.get_chunk_count_for_strategy(strategy)

        assignments: Dict[str, Dict[int, List[ChunkAssignment]]] = {}

        # Get models that need chunking
        models_to_shard = self._get_models_for_sharding(strategy)
        if not models_to_shard:
            logger.debug("No models to shard")
            return {}

        for model in models_to_shard:
            model_assignments = await self._assign_model_chunks(
                model, num_chunks, replication, eligible_peers, strategy
            )
            if model_assignments is None:
                # Failed to assign chunks for this model — skip it (it'll use routing)
                logger.warning(f"Failed to assign chunks for {model}, will use routing fallback")
                continue
            assignments[model] = model_assignments

        return assignments if assignments else None

    def get_chunk_count_for_strategy(self, strategy: Strategy) -> int:
        """Get the target chunk count for a strategy."""
        base = CHUNK_COUNT.get(strategy.value, 1)
        # Adjust based on peer count
        eligible = len(self._get_eligible_peers())
        # Don't create more chunks than peers / replication factor
        if strategy != Strategy.ROUTING and eligible > 0:
            max_by_peers = max(1, eligible // max(1, self.get_replication_factor(strategy)))
            return min(base, max_by_peers, MAX_CHUNKS_PER_MODEL)
        return base

    def _get_models_for_sharding(self, strategy: Strategy) -> List[str]:
        """Get list of models that should be sharded under this strategy."""
        models = set()

        # Models we know about locally
        if self.resource_guard and hasattr(self.resource_guard, 'enabled'):
            # Get models from Resource Guard config if available
            pass

        # Models from tracker (peers' models)
        for peer in self._get_eligible_peers():
            for model in peer.models:
                if self._validator.validate_model_name(model):
                    models.add(model)

        # Models from our config
        known_models = set(self._model_sizes.keys())
        models.update(known_models)

        return sorted(models)

    async def _assign_model_chunks(
        self,
        model: str,
        num_chunks: int,
        replication: int,
        peers: List[PeerInfo],
        strategy: Strategy
    ) -> Optional[Dict[int, List[ChunkAssignment]]]:
        """Assign chunks of a model to peers.

        Strategy-aware assignment:
          - routing: no chunks
          - partial_sharding: prefer GPU peers for first chunks
          - full_sharding: balanced distribution
          - raid_ram: maximize distribution + pre-fetch

        Args:
            model: Model name
            num_chunks: Number of chunks to create
            replication: Number of replicas per chunk
            peers: List of eligible peers
            strategy: Current strategy

        Returns:
            Dict of chunk_index -> [ChunkAssignment] or None on failure
        """
        if num_chunks < 1:
            return None

        # Sort peers for optimal assignment
        sorted_peers = self._sort_peers_for_assignment(peers, strategy)

        # Model size for chunk sizing
        model_size_mb = self._model_sizes.get(model, 2000)  # default 2GB
        chunk_size_mb = max(1, model_size_mb // num_chunks)

        assignments: Dict[int, List[ChunkAssignment]] = {}

        # Track which peers have chunks (avoid double-assigning)
        peer_load: Dict[str, int] = {p.node_id: 0 for p in sorted_peers}

        for chunk_idx in range(num_chunks):
            chunk_replicas = []

            for replica_idx in range(replication):
                # Find the best peer for this chunk replica
                peer = self._find_best_peer_for_chunk(
                    chunk_idx, replica_idx, sorted_peers, peer_load, strategy
                )

                if peer is None:
                    # Not enough peers for this replication level
                    if replica_idx == 0:
                        # Can't even place the primary — fail
                        return None
                    # Can't place a replica — skip (partial replication is ok)
                    logger.debug(f"Could not place replica {replica_idx} of "
                                f"chunk {chunk_idx} for {model}")
                    continue

                assignment = ChunkAssignment(
                    model=model,
                    chunk_index=chunk_idx,
                    total_chunks=num_chunks,
                    peer_id=peer.node_id,
                    peer_address=peer.address,
                    size_mb=chunk_size_mb,
                    is_replica=(replica_idx > 0),
                    verified=False,
                )
                chunk_replicas.append(assignment)
                peer_load[peer.node_id] = peer_load.get(peer.node_id, 0) + 1

            if chunk_replicas:
                assignments[chunk_idx] = chunk_replicas

        # Verify we have at least primary assignments for all chunks
        for chunk_idx in range(num_chunks):
            if chunk_idx not in assignments:
                return None
            primaries = [a for a in assignments[chunk_idx] if not a.is_replica]
            if not primaries:
                return None

        return assignments

    def _sort_peers_for_assignment(self, peers: List[PeerInfo],
                                    strategy: Strategy) -> List[PeerInfo]:
        """Sort peers for optimal chunk assignment.

        For routing/partial_sharding: GPU peers first, then by RAM
        For full_sharding: balanced by current load
        For raid_ram: maximize distribution
        """
        if strategy in (Strategy.ROUTING, Strategy.PARTIAL_SHARDING):
            # GPU peers first, then by RAM (descending), then by score
            return sorted(peers, key=lambda p: (
                not p.gpu_available,  # GPU first
                -p.effective_ram,      # More RAM first
                -p.score,              # Higher score first
            ))
        elif strategy == Strategy.FULL_SHARDING:
            # Balanced: mix GPU and CPU, prefer higher uptime
            return sorted(peers, key=lambda p: (
                -p.uptime_seconds,  # Higher uptime first
                -p.score,
                -p.effective_ram,
            ))
        else:  # RAID_RAM
            # Maximize distribution: sort by bandwidth, then RAM
            return sorted(peers, key=lambda p: (
                -p.bandwidth_kbps,
                -p.effective_ram,
                -p.score,
            ))

    def _find_best_peer_for_chunk(
        self,
        chunk_idx: int,
        replica_idx: int,
        peers: List[PeerInfo],
        peer_load: Dict[str, int],
        strategy: Strategy,
    ) -> Optional[PeerInfo]:
        """Find the best peer for a specific chunk replica.

        Considers:
          - Current load (avoid overloading peers)
          - Resource Guard limits (never exceed what user allows)
          - Strategy preferences (GPU for first chunks, etc.)
          - Malicious node detection (skip banned nodes)
        """
        # Filter out overloaded and banned peers
        max_load = 3 if strategy == Strategy.RAID_RAM else 2

        candidates = []
        for peer in peers:
            # Skip banned nodes
            if self._malicious_detector.is_banned(peer.node_id):
                continue
            # Skip stale peers
            if peer.is_stale:
                continue
            # Check load
            current_load = peer_load.get(peer.node_id, 0)
            if current_load >= max_load:
                continue
            # Check if peer has enough RAM for a chunk
            if peer.effective_ram < 256:  # Minimum 256 MB per chunk
                continue
            candidates.append(peer)

        if not candidates:
            return None

        # Sort by load (ascending), then by preference
        candidates.sort(key=lambda p: (
            peer_load.get(p.node_id, 0),   # Less loaded first
            not p.gpu_available,            # GPU first (if relevant)
            -p.effective_ram,              # More RAM first
            -p.score,                      # Higher score first
        ))

        # For replicas, try to pick a different peer than the primary
        if replica_idx > 0 and len(candidates) > 1:
            # Move primary peer to end of list
            primary_assignment = self._get_primary_peer_for_chunk(chunk_idx)
            if primary_assignment:
                primary_id = primary_assignment.peer_id
                same_peer = [c for c in candidates if c.node_id == primary_id]
                other_peers = [c for c in candidates if c.node_id != primary_id]
                if other_peers:
                    candidates = other_peers + same_peer

        return candidates[0]

    def _get_primary_peer_for_chunk(self, chunk_idx: int) -> Optional[ChunkAssignment]:
        """Get the primary (non-replica) assignment for a chunk."""
        for model_chunks in self._chunk_assignments.values():
            if chunk_idx in model_chunks:
                for assignment in model_chunks[chunk_idx]:
                    if not assignment.is_replica:
                        return assignment
        return None

    # ===================================================================
    # CHUNK REDISTRIBUTION
    # ===================================================================

    async def redistribute_chunks(self):
        """Rebalance chunks when peers join/leave.

        Called periodically or when peer availability changes.
        Reassigns chunks from departed/stale peers to available ones.
        """
        if self._strategy == Strategy.ROUTING:
            return  # No chunks to redistribute

        now = time.time()
        if (now - self._last_redistribution) < REDISTRIBUTION_COOLDOWN:
            return

        self._last_redistribution = now

        # Check for chunks that need reassignment
        needs_redistribution = False
        stale_peer_ids: Set[str] = set()

        for model, chunks in self._chunk_assignments.items():
            for chunk_idx, assignments in chunks.items():
                for assignment in assignments:
                    peer = self._peers.get(assignment.peer_id)
                    if peer is None or peer.is_stale or self._malicious_detector.is_banned(assignment.peer_id):
                        needs_redistribution = True
                        stale_peer_ids.add(assignment.peer_id)

        if not needs_redistribution:
            return

        logger.info(f"AdaptiveScheduler: redistributing chunks "
                    f"(stale peers: {stale_peer_ids})")

        # Re-prepare chunk assignments with current eligible peers
        new_assignments = await self._prepare_chunk_assignments(self._strategy)

        if new_assignments is not None:
            with self._lock:
                self._chunk_assignments = new_assignments
            logger.info("AdaptiveScheduler: redistribution complete")
        else:
            # Can't redistribute — fall back to routing
            logger.warning("AdaptiveScheduler: redistribution failed, falling back to routing")
            await self._fallback()

        # Notify callback
        if self._on_redistribution:
            try:
                await self._on_redistribution(stale_peer_ids)
            except Exception as e:
                logger.error(f"Redistribution callback error: {e}")

    # ===================================================================
    # QUERY ROUTING
    # ===================================================================

    async def route_query(self, prompt: str, model: str) -> Dict[str, Any]:
        """Route a query using the current strategy.

        This is the main entry point for query routing.

        Args:
            prompt: The user's prompt
            model: The model to query

        Returns:
            Dict with routing information:
              - strategy: current strategy name
              - target_node: node to send the query to
              - target_address: address of the target node
              - chunks: chunk assignments (for sharded strategies)
              - fallback: True if this is a fallback routing
        """
        # Validate inputs
        if not self._validator.validate_model_name(model):
            raise ValueError(f"Invalid model name: {model}")
        if not self._validator.validate_prompt(prompt):
            raise ValueError(f"Invalid prompt: exceeds {MAX_PROMPT_LENGTH} characters")

        # Rate limit
        if not self._routing_limiter.allow(f"query:{model}"):
            raise RuntimeError("Rate limit exceeded for query routing")

        # Check Resource Guard
        if not self.resource_guard.can_accept_request(
            prompt_length=len(prompt)
        ):
            raise RuntimeError("Resource Guard: cannot accept request now")

        strategy = self._strategy

        if strategy == Strategy.ROUTING:
            return await self._route_simple(prompt, model)
        elif strategy == Strategy.PARTIAL_SHARDING:
            return await self._route_sharded(prompt, model)
        elif strategy == Strategy.FULL_SHARDING:
            return await self._route_sharded(prompt, model)
        else:  # RAID_RAM
            return await self._route_raid(prompt, model)

    async def _route_simple(self, prompt: str, model: str) -> Dict[str, Any]:
        """Route a query to a single node (routing strategy).

        Selects the best available node that can serve the model.
        Falls back to local if no suitable peer is found.
        """
        eligible = self._get_eligible_peers()

        # Filter peers that have the model
        model_peers = [p for p in eligible if model in p.models]

        if model_peers:
            # Select best peer (highest score, most resources)
            best = max(model_peers, key=lambda p: (p.score, p.effective_ram))
            return {
                "strategy": "routing",
                "target_node": best.node_id,
                "target_address": best.address,
                "chunks": {},
                "fallback": False,
            }

        # No peer has the model — route locally
        return {
            "strategy": "routing",
            "target_node": "local",
            "target_address": "localhost",
            "chunks": {},
            "fallback": True,
        }

    async def _route_sharded(self, prompt: str, model: str) -> Dict[str, Any]:
        """Route a query through sharded model (partial or full sharding).

        Pipeline parallel: prompt goes through chunk 1, then chunk 2, etc.
        If sharding fails for this model, fall back to routing.
        """
        if model not in self._chunk_assignments:
            # No chunks for this model — fall back to routing
            logger.debug(f"No chunk assignments for {model}, falling back to routing")
            result = await self._route_simple(prompt, model)
            result["fallback"] = True
            return result

        chunks = self._chunk_assignments[model]
        if not chunks:
            result = await self._route_simple(prompt, model)
            result["fallback"] = True
            return result

        # Build the pipeline: chunk 0 -> chunk 1 -> ... -> chunk N
        pipeline: List[Dict] = []
        for chunk_idx in sorted(chunks.keys()):
            assignments = chunks[chunk_idx]
            # Use primary assignment (not replica) for the pipeline
            primary = None
            for a in assignments:
                if not a.is_replica:
                    primary = a
                    break
            if primary is None:
                # No primary — use first available
                primary = assignments[0]

            pipeline.append({
                "chunk_index": primary.chunk_index,
                "total_chunks": primary.total_chunks,
                "primary_node": primary.peer_id,
                "primary_address": primary.peer_address,
                "replicas": [
                    {
                        "node": a.peer_id,
                        "address": a.peer_address,
                    }
                    for a in assignments if a.is_replica
                ],
                "size_mb": primary.size_mb,
            })

        return {
            "strategy": self._strategy.value,
            "target_node": pipeline[0]["primary_node"] if pipeline else "local",
            "target_address": pipeline[0]["primary_address"] if pipeline else "localhost",
            "chunks": pipeline,
            "fallback": False,
        }

    async def _route_raid(self, prompt: str, model: str) -> Dict[str, Any]:
        """Route a query through RAID RAM distributed inference.

        Similar to sharded but with:
          - Pre-fetching of adjacent chunks
          - 3x replication
          - Async chunk loading
        """
        result = await self._route_sharded(prompt, model)
        if result.get("strategy") == "routing":
            result["fallback"] = True
            return result

        # Add RAID-specific info
        result["strategy"] = "raid_ram"
        result["prefetch"] = True
        result["replication_factor"] = self.get_replication_factor(Strategy.RAID_RAM)

        return result

    # ===================================================================
    # PEER MANAGEMENT
    # ===================================================================

    async def _fetch_available_peers(self) -> List[PeerInfo]:
        """Fetch available peers from tracker and local discovery.

        Returns:
            List of PeerInfo objects for eligible peers
        """
        peers: Dict[str, PeerInfo] = {}

        # From tracker
        if self.tracker_client:
            try:
                tracker_nodes = self.tracker_client.get_known_nodes()
                for node_data in tracker_nodes:
                    peer = self._validator.sanitize_peer_data(node_data)
                    if peer and not peer.is_stale:
                        peers[peer.node_id] = peer
            except Exception as e:
                logger.debug(f"Error fetching peers from tracker: {e}")

        # Update internal peer list
        with self._lock:
            # Add new peers
            for node_id, peer in peers.items():
                if node_id in self._peers:
                    # Update existing peer info
                    existing = self._peers[node_id]
                    existing.last_seen = peer.last_seen
                    existing.models = peer.models
                    existing.score = peer.score
                    existing.ram_share_mb = peer.ram_share_mb
                    existing.cpu_cores = peer.cpu_cores
                    existing.gpu_available = peer.gpu_available
                    existing.bandwidth_kbps = peer.bandwidth_kbps
                else:
                    self._peers[node_id] = peer

            # Remove stale peers
            stale_ids = [nid for nid, p in self._peers.items() if p.is_stale]
            for nid in stale_ids:
                del self._peers[nid]

        return list(self._peers.values())

    def add_peer(self, peer_data: Dict):
        """Manually add or update a peer.

        Args:
            peer_data: Dict with peer information (validated internally)
        """
        peer = self._validator.sanitize_peer_data(peer_data)
        if peer:
            with self._lock:
                self._peers[peer.node_id] = peer

    def remove_peer(self, node_id: str):
        """Remove a peer from the scheduler.

        Args:
            node_id: Node ID to remove
        """
        with self._lock:
            self._peers.pop(node_id, None)

    def _get_eligible_peers(self) -> List[PeerInfo]:
        """Get peers eligible for chunk assignment.

        Excludes:
          - Stale peers
          - Banned peers
          - Peers with insufficient resources
        """
        with self._lock:
            eligible = []
            for peer in self._peers.values():
                if peer.is_stale:
                    continue
                if self._malicious_detector.is_banned(peer.node_id):
                    continue
                if peer.effective_ram < 128:  # Minimum 128 MB
                    continue
                eligible.append(peer)
            return eligible

    # ===================================================================
    # RESOURCE GUARD INTEGRATION
    # ===================================================================

    def _check_resource_guard(self) -> bool:
        """Check if Resource Guard allows us to operate.

        Returns:
            True if we can proceed with the current strategy
        """
        if not self.resource_guard:
            return True  # No guard = no restrictions

        if not self.resource_guard.enabled:
            return True  # Disabled guard

        resources = self.resource_guard.get_available_resources()
        return resources.get("can_accept", False)

    def get_local_resource_contribution(self) -> Dict[str, Any]:
        """Get what this node can contribute based on Resource Guard limits.

        Returns:
            Dict with available resources for announcement
        """
        if not self.resource_guard:
            return {
                "ram_mb": 0,
                "cpu_available_percent": 0,
                "gpu": False,
                "can_accept": False,
            }
        return self.resource_guard.get_available_resources()

    # ===================================================================
    # HEALTH CHECKS
    # ===================================================================

    async def _health_check_loop(self):
        """Periodically verify that chunk assignments are still valid."""
        while self._running:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                if not self._running:
                    break
                await self._verify_chunk_assignments()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _verify_chunk_assignments(self):
        """Verify that all chunk assignments point to valid, reachable peers."""
        if self._strategy == Strategy.ROUTING:
            return  # No chunks to verify

        stale_assignments = []

        with self._lock:
            for model, chunks in self._chunk_assignments.items():
                for chunk_idx, assignments in chunks.items():
                    for assignment in assignments:
                        peer = self._peers.get(assignment.peer_id)
                        # Check if peer is still valid
                        if peer is None or peer.is_stale or self._malicious_detector.is_banned(assignment.peer_id):
                            stale_assignments.append((model, chunk_idx, assignment))
                        else:
                            # Mark as verified
                            assignment.verified = True
                            assignment.last_verified = time.time()

        # If we found stale assignments, trigger redistribution
        if stale_assignments:
            logger.info(f"Found {len(stale_assignments)} stale chunk assignments, "
                       "triggering redistribution")
            await self.redistribute_chunks()

    async def _update_loop(self):
        """Background loop that periodically updates strategy."""
        while self._running:
            try:
                await asyncio.sleep(self._strategy_update_interval)
                if not self._running:
                    break
                await self.update_strategy()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Strategy update error: {e}")

    # ===================================================================
    # TASK COMPLETION TRACKING
    # ===================================================================

    def record_task_success(self, node_id: str):
        """Record that a task completed successfully on a node."""
        self._malicious_detector.record_success(node_id)

    def record_task_failure(self, node_id: str):
        """Record that a task failed on a node."""
        self._malicious_detector.record_failure(node_id)

    def record_false_claim(self, node_id: str):
        """Record that a node claimed capabilities it doesn't have."""
        self._malicious_detector.record_false_claim(node_id)

    # ===================================================================
    # PUBLIC API
    # ===================================================================

    @property
    def strategy(self) -> Strategy:
        """Current strategy."""
        return self._strategy

    @property
    def transition_state(self) -> TransitionState:
        """Current transition state."""
        return self._transition_state

    @property
    def peer_count(self) -> int:
        """Number of eligible peers."""
        return len(self._get_eligible_peers())

    def get_status(self) -> Dict[str, Any]:
        """Get full scheduler status for monitoring/dashboards."""
        with self._lock:
            chunk_info = {}
            for model, chunks in self._chunk_assignments.items():
                model_chunks = {}
                for idx, assignments in chunks.items():
                    model_chunks[idx] = [a.to_dict() for a in assignments]
                chunk_info[model] = model_chunks

            return {
                "strategy": self._strategy.value,
                "transition_state": self._transition_state.value,
                "peer_count": len(self._peers),
                "eligible_peers": len(self._get_eligible_peers()),
                "replication_factor": self.get_replication_factor(),
                "models_sharded": list(self._chunk_assignments.keys()),
                "chunk_assignments": chunk_info,
                "fallback_count": self._fallback_count,
                "last_fallback": self._last_fallback_time,
                "consecutive_failures": self._consecutive_failures,
                "banned_nodes": len(self._malicious_detector.get_banned_nodes()),
                "resource_guard": self.get_local_resource_contribution(),
                "previous_strategy": self._previous_strategy.value if self._previous_strategy else None,
            }

    def get_peers(self) -> List[Dict]:
        """Get list of all known peers."""
        with self._lock:
            return [p.to_dict() for p in self._peers.values() if not p.is_stale]

    def get_chunk_map(self, model: str = None) -> Dict:
        """Get the current chunk assignment map.

        Args:
            model: Optional model name to filter by

        Returns:
            Dict of chunk assignments
        """
        with self._lock:
            if model:
                if model in self._chunk_assignments:
                    return {
                        idx: [a.to_dict() for a in assignments]
                        for idx, assignments in self._chunk_assignments[model].items()
                    }
                return {}
            return {
                m: {
                    idx: [a.to_dict() for a in assignments]
                    for idx, assignments in chunks.items()
                }
                for m, chunks in self._chunk_assignments.items()
            }

    def set_model_sizes(self, sizes: Dict[str, int]):
        """Update model size information (MB per model).

        Args:
            sizes: Dict of model_name -> size_in_mb
        """
        with self._lock:
            for model, size in sizes.items():
                if self._validator.validate_model_name(model):
                    self._model_sizes[model] = max(1, min(size, 1_000_000))

    def force_strategy(self, strategy_name: str) -> bool:
        """Force a specific strategy (for testing or manual override).

        Args:
            strategy_name: One of 'routing', 'partial_sharding', 'full_sharding', 'raid_ram'

        Returns:
            True if strategy was set, False if invalid
        """
        try:
            new_strategy = Strategy(strategy_name)
            with self._lock:
                self._previous_strategy = self._strategy
                self._strategy = new_strategy
                if new_strategy == Strategy.ROUTING:
                    self._chunk_assignments = {}
            self._transition_state = TransitionState.STABLE
            logger.info(f"AdaptiveScheduler: strategy forced to {new_strategy.value}")
            return True
        except ValueError:
            logger.warning(f"Invalid strategy name: {strategy_name}")
            return False

    def to_dict(self) -> Dict:
        """Serialize scheduler state."""
        return {
            "strategy": self._strategy.value,
            "transition_state": self._transition_state.value,
            "peer_count": len(self._peers),
            "eligible_peers": len(self._get_eligible_peers()),
            "replication_factor": self.get_replication_factor(),
            "fallback_count": self._fallback_count,
            "consecutive_failures": self._consecutive_failures,
            "banned_nodes": len(self._malicious_detector.get_banned_nodes()),
        }