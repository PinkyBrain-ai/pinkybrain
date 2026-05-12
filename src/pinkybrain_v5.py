#!/usr/bin/env python3
"""
🌐 PINKYBRAIN v5.2.0 — RÉSEAU P2P DISTRIBUÉ
===============================================
v5.2.0 release:
1. Model Specialist — 12 specialty schemas with auto-detection and multi-LLM routing
2. Multi-Model Executor — 6 modes (single, vote, chain, fuse, compare, specialist)
3. Web UI specialist controls — specialty select, multi-mode select, multi-model rendering
4. i18n — 18 specialty keys in 8 languages
5. API: /api/specialties, /api/specialties/{name}/models, /api/multi
6. Bug fixes and cleanup — removed dead code (v3 archive, nested sub-packages)

v5.0 Major release:
1. Resource Guard — auto-pause/resume mesh sharing based on local user activity
2. Adaptive Scheduler — strategy selection (routing/partial_sharding/full_sharding/raid_ram)
3. Conversation Store — persistent conversations with search, export, privacy levels, encryption
4. Model Share Manager — secure bridge between private models and public mesh (symlinks, SHA-256)
5. Tracker Client — public mesh discovery with Ed25519 signing, rate limiting, backoff
6. Desktop Web UI — 4-tab interface (Chat, Share, Network, Config) with i18n (8 languages)
7. Security hardening — path-based auth tokens, input validation, CORS, rate limiting on all endpoints
8. P2P secret from env var only (no hardcoded secrets)
9. 18 new API endpoints for chat, resources, models, network, config
10. CLI v5 with 15 subcommands

Features preserved from v4:
- mDNS Zero-Config Discovery
- GPU/CPU Model Negotiation
- Gamified Score Dashboard
- Auto-Update
- Systray Support
- Multi-LLM provider support
- WebSocket temps réel
- Ed25519 Auth + Web of Trust
- CRDT Memory Sync
- Circuit Breaker
"""

import asyncio
import aiohttp
from aiohttp import web
import json
import time
import socket
import os
import re
import uuid
import logging
import hashlib
import threading
import html
import secrets as _secrets
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import deque

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
from pathlib import Path
import logging.handlers

# ============================================================================
# v5 MODULE IMPORTS
# ============================================================================

try:
    from resource_guard import ResourceGuard, GuardState
    HAS_RESOURCE_GUARD = True
except ImportError:
    HAS_RESOURCE_GUARD = False
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("resource_guard not available — mesh sharing will not be auto-protected")

try:
    from adaptive_scheduler import AdaptiveScheduler, Strategy as SchedulerStrategy
    HAS_ADAPTIVE_SCHEDULER = True
except ImportError:
    HAS_ADAPTIVE_SCHEDULER = False
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("adaptive_scheduler not available — using basic routing")

try:
    from conversation_store import ConversationStore, PrivacyLevel as ConvPrivacyLevel
    HAS_CONVERSATION_STORE = True
except ImportError:
    HAS_CONVERSATION_STORE = False
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("conversation_store not available — conversations will not persist")

try:
    from model_share_manager import ModelShareManager
    HAS_MODEL_SHARE_MANAGER = True
except ImportError:
    HAS_MODEL_SHARE_MANAGER = False
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("model_share_manager not available — model sharing disabled")

try:
    from tracker_client import TrackerClient, TrackerState, KnownNode
    HAS_TRACKER_CLIENT = True
except ImportError:
    HAS_TRACKER_CLIENT = False

try:
    from model_specialist import (
        ModelSpecialty, ModelProfile, SpecialistRouter,
        MultiModelMode, MultiModelResult, MultiModelExecutor,
    )
    HAS_MODEL_SPECIALIST = True
except ImportError:
    HAS_MODEL_SPECIALIST = False

try:
    from bandwidth_quota import BandwidthQuota, QuotaPeriod
    HAS_BANDWIDTH_QUOTA = True
except ImportError:
    HAS_BANDWIDTH_QUOTA = False

try:
    from credit_system import CreditSystem, CreditTier, QUERY_COSTS, MONTHLY_REWARDS, BASE_ALLOCATION
    HAS_CREDIT_SYSTEM = True
except ImportError:
    HAS_CREDIT_SYSTEM = False
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("model_specialist not available — specialty routing disabled")
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("tracker_client not available — public mesh discovery disabled")

try:
    from model_registry import ModelRegistry, ModelCard, ModelSource, ModelStatus
    HAS_MODEL_REGISTRY = True
except ImportError:
    HAS_MODEL_REGISTRY = False
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("model_registry not available — model catalog disabled")

try:
    from network_sync import NetworkSync, DynamicDNS, NODE_STALE_THRESHOLD_DAYS, MODEL_STALE_THRESHOLD_DAYS
    HAS_NETWORK_SYNC = True
except ImportError:
    HAS_NETWORK_SYNC = False
    logger_v5 = logging.getLogger('PinkyBrain.v5')
    logger_v5.warning("network_sync not available — automatic mesh sync disabled")

# ============================================================================
# SECURITY CONSTANTS
# ============================================================================

MAX_PROMPT_LENGTH = 50000  # 50KB max prompt
ALLOWED_MODEL_PATTERN = re.compile(r'^[a-zA-Z0-9._:/-]+$')
ALLOWED_STRATEGIES = {'auto', 'local', 'peer', 'consensus', 'chain'}
GLOBAL_RATE_LIMIT_RATE = 30.0  # requests per second globally
GLOBAL_RATE_LIMIT_BURST = 60
AUTH_TIMEOUT_SECONDS = 10  # WebSocket auth timeout

# Security constants (v5.2)
MAX_KEY_LENGTH = 256          # Max CRDT key length
MAX_VALUE_SIZE = 102400      # Max CRDT value size (100KB)
MAX_TTL = 86400              # Max TTL (24h)
MAX_SYNC_ENTRIES = 1000       # Max entries per P2P sync push
WS_MAX_MSG_SIZE = 1048576     # Max WebSocket message size (1MB)
HMAC_WINDOW_SECONDS = 30     # HMAC timestamp window (30s)
MAX_NONCE_CACHE = 10000      # Max nonce cache size
CSP_HEADER = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:"

# CORS allowed origins (configurable)
CORS_ALLOWED_ORIGINS = [
    'http://localhost',
    'http://127.0.0.1',
]

# ============================================================================
# LOGGING
# ============================================================================

log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
# LOW-01: Restrict log directory permissions
try:
    log_dir.chmod(0o700)
except OSError:
    pass
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger('PinkyBrain')
file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "pinkybrain.log", maxBytes=5*1024*1024, backupCount=3
)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


# ============================================================================
# mDNS Zero-Config Discovery
# ============================================================================

class ZeroConfigDiscovery:
    """mDNS-style zero-config peer discovery on local network.
    
    Uses UDP broadcast + multicast for LAN auto-discovery.
    Two nodes on the same network find each other without any IP config.
    """
    
    BROADCAST_PORT = 8090
    MULTICAST_ADDR = '224.0.0.251'  # mDNS multicast address
    MULTICAST_PORT = 5353
    BEACON_INTERVAL = 60  # seconds between broadcasts
    
    def __init__(self, node_name: str, own_port: int, capabilities: Dict = None):
        self.node_name = node_name
        self.own_port = own_port
        self.capabilities = capabilities or {}
        self._running = False
        self._beacon_task = None
        self._listener_task = None
        self._found_peers: Dict[str, Dict] = {}  # name -> info
        self._local_ip = self._get_local_ip()
    
    def _get_local_ip(self) -> str:
        """Get this machine's local network IP."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return '127.0.0.1'
    
    def _get_broadcast_addr(self) -> str:
        """Derive broadcast address from local IP."""
        parts = self._local_ip.split('.')
        return f'{parts[0]}.{parts[1]}.{parts[2]}.255'
    
    def _build_beacon(self) -> bytes:
        """Build discovery beacon message."""
        return json.dumps({
            'type': 'pinkybrain_discovery',
            'version': '5.2.0',
            'node': self.node_name,
            'port': self.own_port,
            'ip': self._local_ip,
            'capabilities': self.capabilities,
            'ts': time.time()
        }).encode()
    
    def _parse_beacon(self, data: bytes, addr: tuple) -> Optional[Dict]:
        """Parse an incoming discovery beacon."""
        try:
            msg = json.loads(data.decode())
            if msg.get('type') != 'pinkybrain_discovery':
                return None
            if msg['node'] == self.node_name:
                return None  # ignore self
            if time.time() - msg.get('ts', 0) > 120:
                return None  # stale beacon
            return {
                'name': msg['node'],
                'host': msg.get('ip', addr[0]),
                'port': msg['port'],
                'capabilities': msg.get('capabilities', {}),
                'ts': msg['ts']
            }
        except (json.JSONDecodeError, KeyError):
            return None
    
    async def start(self):
        """Start broadcasting and listening."""
        if self._running:
            return
        self._running = True
        self._beacon_task = asyncio.create_task(self._beacon_loop())
        self._listener_task = asyncio.create_task(self._listener_loop())
        logger.info(f"📡 Zero-Config Discovery started on port {self.BROADCAST_PORT}")
    
    async def stop(self):
        """Stop discovery."""
        self._running = False
        if self._beacon_task:
            self._beacon_task.cancel()
        if self._listener_task:
            self._listener_task.cancel()
    
    async def _beacon_loop(self):
        """Periodically broadcast our presence."""
        while self._running:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._send_beacon)
            except Exception as e:
                logger.debug(f"Beacon error: {e}")
            await asyncio.sleep(self.BEACON_INTERVAL)
    
    def _send_beacon(self):
        """Send UDP broadcast beacon."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2)
            msg = self._build_beacon()
            # Broadcast to derived subnet + common subnets
            targets = [self._get_broadcast_addr()]
            for target in targets:
                try:
                    sock.sendto(msg, (target, self.BROADCAST_PORT))
                except OSError:
                    pass
            # Also send multicast for mDNS-style discovery
            try:
                sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock2.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                sock2.sendto(msg, (self.MULTICAST_ADDR, self.MULTICAST_PORT))
                sock2.close()
            except OSError:
                pass
            sock.close()
        except OSError:
            pass
    
    async def _listener_loop(self):
        """Listen for discovery beacons from other nodes."""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                peers = await loop.run_in_executor(None, self._listen_once)
                for p in peers:
                    name = p['name']
                    if name not in self._found_peers or p['ts'] > self._found_peers[name]['ts']:
                        self._found_peers[name] = p
                        logger.info(f"📡 Zero-Config: discovered {name} at {p['host']}:{p['port']}")
            except Exception as e:
                logger.debug(f"Listener error: {e}")
            await asyncio.sleep(5)
    
    def _listen_once(self) -> List[Dict]:
        """Single listening pass for beacons."""
        found = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(3)
            sock.bind(('', self.BROADCAST_PORT))
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    peer = self._parse_beacon(data, addr)
                    if peer:
                        found.append(peer)
                except socket.timeout:
                    break
            sock.close()
        except OSError:
            pass
        return found
    
    def get_discovered_peers(self) -> List[Dict]:
        """Return all auto-discovered peers."""
        # Prune stale peers (>5 min)
        now = time.time()
        stale = [n for n, p in self._found_peers.items() if now - p['ts'] > 300]
        for n in stale:
            del self._found_peers[n]
        return list(self._found_peers.values())


# ============================================================================
# GPU/CPU Capability Negotiation
# ============================================================================

class NodeCapabilities:
    """Detect and advertise node hardware capabilities.
    
    Nodes tell each other what they can run:
    - GPU: nvidia-smi detection, VRAM size
    - CPU: cores, RAM
    - Models: size categories they can handle
    """
    
    # Model size thresholds (approximate parameter count)
    SIZE_CATEGORIES = {
        'tiny': 3_000_000_000,      # <3B params (e.g., phi-2)
        'small': 8_000_000_000,     # <8B params (e.g., llama-3-8b)
        'medium': 35_000_000_000,  # <35B params (e.g., command-r)
        'large': 70_000_000_000,   # <70B params (e.g., llama-3-70b)
        'xl': float('inf')         # >70B params
    }
    
    def __init__(self):
        self.gpu_available = False
        self.gpu_name = ''
        self.gpu_vram_mb = 0
        self.cpu_cores = 0
        self.cpu_freq_mhz = 0
        self.ram_total_mb = 0
        self.max_model_category = 'small'  # default: CPU can handle small
        self._detect()
    
    def _detect(self):
        """Auto-detect hardware capabilities."""
        try:
            if HAS_PSUTIL:
                self.cpu_cores = psutil.cpu_count(logical=True) or 4
                self.ram_total_mb = psutil.virtual_memory().total // (1024 * 1024)
                freq = psutil.cpu_freq()
            else:
                self.cpu_cores = os.cpu_count() or 4
                self.ram_total_mb = 2560  # fallback: 2.5GB default
                freq = None
            self.cpu_freq_mhz = int(freq.current) if freq else 0
        except Exception:
            self.cpu_cores = 4
            self.ram_total_mb = 4096
        
        # GPU detection
        self._detect_gpu()
        
        # Determine max model category
        self.max_model_category = self._estimate_max_model()
    
    def _detect_gpu(self):
        """Try to detect NVIDIA GPU via nvidia-smi."""
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                self.gpu_name = parts[0].strip()
                self.gpu_vram_mb = int(parts[1].strip()) if len(parts) > 1 else 0
                self.gpu_available = True
                logger.info(f"🎮 GPU detected: {self.gpu_name} ({self.gpu_vram_mb}MB VRAM)")
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            self.gpu_available = False
    
    def _estimate_max_model(self) -> str:
        """Estimate the largest model category this node can run."""
        if self.gpu_available:
            # GPU: ~2 bytes per parameter for FP16, ~1.3 with offloading
            vram_params = (self.gpu_vram_mb * 1024 * 1024) / 1.5  # rough FP16
            if vram_params >= 70_000_000_000:
                return 'large'
            elif vram_params >= 35_000_000_000:
                return 'medium'
            elif vram_params >= 8_000_000_000:
                return 'small'
            else:
                return 'tiny'
        else:
            # CPU: need ~4 bytes per param (float32), but quantized ~1 byte
            # RAM must be enough for model + OS
            usable_ram = max(self.ram_total_mb - 2048, 0) * 1024 * 1024  # leave 2GB for OS
            if usable_ram >= 16_000_000_000:  # 16GB free = can do ~8B quantized
                return 'small'
            elif usable_ram >= 6_000_000_000:
                return 'tiny'
            else:
                return 'tiny'
    
    def can_run_model(self, model_name: str, model_size: int = 0) -> bool:
        """Check if this node can run a given model."""
        if model_size > 0:
            cat = self._categorize_by_size(model_size)
        else:
            # Heuristic from model name
            cat = self._categorize_by_name(model_name)
        
        cat_order = ['tiny', 'small', 'medium', 'large', 'xl']
        return cat_order.index(cat) <= cat_order.index(self.max_model_category)
    
    def _categorize_by_name(self, name: str) -> str:
        """Guess model size from name heuristics."""
        name_lower = name.lower()
        if any(k in name_lower for k in ['70b', '72b', '405b']):
            return 'large'
        if any(k in name_lower for k in ['35b', '34b', '32b', '30b']):
            return 'medium'
        if any(k in name_lower for k in ['8b', '9b', '7b', '14b', '13b', '12b']):
            return 'small'
        return 'tiny'
    
    def _categorize_by_size(self, size: int) -> str:
        for cat, threshold in self.SIZE_CATEGORIES.items():
            if size < threshold:
                return cat
        return 'xl'
    
    def to_dict(self) -> Dict:
        return {
            'gpu_available': self.gpu_available,
            'gpu_name': self.gpu_name,
            'gpu_vram_mb': self.gpu_vram_mb,
            'cpu_cores': self.cpu_cores,
            'ram_total_mb': self.ram_total_mb,
            'max_model_category': self.max_model_category
        }


class ModelNegotiator:
    """Negotiate model placement across the P2P network.
    
    When a query arrives, the negotiator checks:
    1. What size category is this model?
    2. Which peers can handle it?
    3. Route to the best-capable peer (GPU > CPU for large, local for small)
    """
    
    def __init__(self, own_capabilities: NodeCapabilities):
        self.own_caps = own_capabilities
        self.peer_caps: Dict[str, NodeCapabilities] = {}  # peer_name -> caps
    
    def update_peer_capabilities(self, peer_name: str, caps_dict: Dict):
        """Update capabilities for a peer."""
        caps = NodeCapabilities()
        caps.gpu_available = caps_dict.get('gpu_available', False)
        caps.gpu_name = caps_dict.get('gpu_name', '')
        caps.gpu_vram_mb = caps_dict.get('gpu_vram_mb', 0)
        caps.cpu_cores = caps_dict.get('cpu_cores', 4)
        caps.ram_total_mb = caps_dict.get('ram_total_mb', 4096)
        caps.max_model_category = caps_dict.get('max_model_category', 'tiny')
        self.peer_caps[peer_name] = caps
    
    def select_best_node(self, model: str, peers: List[Any], prefer_local: bool = True) -> Optional[str]:
        """Select the best node to handle a model query.
        
        Strategy:
        - Tiny/small models → local first (fast, low overhead)
        - Medium/large models → GPU peer first, then local if capable
        - If no peer can handle it, return None (cloud fallback)
        """
        model_cat = self.own_caps._categorize_by_name(model)
        
        # For small models, prefer local
        if model_cat in ('tiny', 'small') and prefer_local:
            if self.own_caps.can_run_model(model):
                return 'local'
        
        # For large models, find GPU peers
        if model_cat in ('medium', 'large'):
            best_gpu = None
            best_vram = 0
            for name, caps in self.peer_caps.items():
                if caps.gpu_available and caps.can_run_model(model):
                    if caps.gpu_vram_mb > best_vram:
                        best_gpu = name
                        best_vram = caps.gpu_vram_mb
            if best_gpu:
                return best_gpu
        
        # Fallback: any peer that can run it
        for name, caps in self.peer_caps.items():
            if caps.can_run_model(model):
                return name
        
        # Last resort: local
        if self.own_caps.can_run_model(model):
            return 'local'
        
        return None


# ============================================================================
# Gamified Score System
# ============================================================================

class GamifiedScore:
    """Visual score levels for the dashboard.
    
    Turns the 0-100 numeric score into named tiers
    with badges, encouraging users to keep sharing.
    """
    
    TIERS = [
        (0,   '🌱 Seedling',    '#888888'),
        (10,  '🥉 Bronze',      '#cd7f32'),
        (20,  '🥈 Silver',      '#c0c0c0'),
        (40,  '🥇 Gold',        '#ffd700'),
        (60,  '💎 Platinum',    '#e5e4e2'),
        (80,  '💠 Diamond',     '#b9f2ff'),
        (95,  '🌟 Celestial',   '#ff6b6b'),
    ]
    
    @staticmethod
    def get_tier(score: float) -> Dict:
        """Get tier info for a score."""
        tier_name = GamifiedScore.TIERS[0][1]
        tier_color = GamifiedScore.TIERS[0][2]
        for threshold, name, color in GamifiedScore.TIERS:
            if score >= threshold:
                tier_name = name
                tier_color = color
        next_tier = None
        for threshold, name, color in GamifiedScore.TIERS:
            if score < threshold:
                next_tier = {'name': name, 'score_needed': threshold, 'color': color}
                break
        return {
            'tier': tier_name,
            'color': tier_color,
            'score': score,
            'next_tier': next_tier,
            'progress_pct': min(score, 100)
        }
    
    @staticmethod
    def get_progress_bar(score: float) -> str:
        """Generate a text progress bar for CLI."""
        tier = GamifiedScore.get_tier(score)
        filled = int(score / 2)  # 50 chars max
        bar = '█' * filled + '░' * (50 - filled)
        return f"{tier['tier']} [{bar}] {score:.1f}/100"


# ============================================================================
# Auto-Update Checker
# ============================================================================

class AutoUpdater:
    """Check for PinkyBrain updates on GitHub.
    
    Non-blocking check. Can prompt user or auto-update.
    Preserves the lightweight ethos — only checks on startup + periodic.
    """
    
    GITHUB_API = os.environ.get('PINKYBRAIN_GITHUB_API', 'https://api.github.com/repos/pinkybrain/pinkybrain/releases/latest')
    CURRENT_VERSION = '5.2.0'
    CHECK_INTERVAL = 86400  # once per day
    
    def __init__(self, auto_install: bool = False):
        self.auto_install = auto_install
        self.last_check = 0
        self.latest_version = None
        self.download_url = None
    
    async def check(self) -> Optional[Dict]:
        """Check for updates. Returns update info if available, None if up-to-date."""
        now = time.time()
        if now - self.last_check < self.CHECK_INTERVAL and self.latest_version:
            return self._compare()
        
        self.last_check = now
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.GITHUB_API, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.latest_version = data.get('tag_name', '').lstrip('v')
                        assets = data.get('assets', [])
                        if assets:
                            self.download_url = assets[0].get('browser_download_url')
                        return self._compare()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        return None
    
    def _compare(self) -> Optional[Dict]:
        """Compare current vs latest version."""
        if not self.latest_version:
            return None
        try:
            parts_current = [int(x) for x in self.CURRENT_VERSION.split('.')]
            parts_latest = [int(x) for x in self.latest_version.split('.')]
            if parts_latest > parts_current:
                return {
                    'current': self.CURRENT_VERSION,
                    'latest': self.latest_version,
                    'download_url': self.download_url,
                    'auto_install': self.auto_install
                }
        except (ValueError, IndexError):
            pass
        return None


# ============================================================================
# Systray Daemon
# ============================================================================

class SystrayDaemon:
    """Run PinkyBrain as a background systray daemon.
    
    On Linux: uses systemd user service (already exists)
    On future: can integrate with pystray for GUI tray icon
    For now: manages the daemon lifecycle and provides status.
    """
    
    def __init__(self, node_name: str, pid_file: str = None):
        self.node_name = node_name
        self.pid_file = pid_file or os.path.expanduser('~/.pinkybrain/daemon.pid')
        self._ensure_dir()
    
    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
    
    def write_pid(self, pid: int):
        """Write PID file for daemon mode."""
        # LOW-02: Restrict PID file permissions
        os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
        with open(self.pid_file, 'w') as f:
            f.write(str(pid))
        try:
            os.chmod(self.pid_file, 0o600)
        except OSError:
            pass
    
    def read_pid(self) -> Optional[int]:
        """Read daemon PID."""
        try:
            with open(self.pid_file) as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return None
    
    def is_running(self) -> bool:
        """Check if daemon is running."""
        pid = self.read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)  # signal 0 = check existence
            return True
        except OSError:
            return False
    
    def status(self) -> Dict:
        """Get daemon status."""
        running = self.is_running()
        pid = self.read_pid() if running else None
        return {
            'daemon_running': running,
            'pid': pid,
            'pid_file': self.pid_file,
            'mode': 'systray' if running else 'stopped'
        }


# ============================================================================
# FEATURE 2: ED25519 IDENTITY & WEB OF TRUST
# ============================================================================

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError
    HAS_NACL = True
except ImportError:
    HAS_NACL = False
    logger.info("PyNaCl not available — using HMAC fallback for Ed25519 identity")


class NodeIdentity:
    """Ed25519-based node identity. Self-generated, no central registry.
    Falls back to HMAC if PyNaCl is not installed.
    """
    def __init__(self, name: str, secret_seed: str = None):
        self.name = name
        self.created = time.time()

        if HAS_NACL:
            if secret_seed:
                seed = hashlib.sha256(secret_seed.encode()).digest()[:32]
                self._signing_key = SigningKey(seed)
            else:
                self._signing_key = SigningKey.generate()
            self._verify_key = self._signing_key.verify_key
            self.public_key_hex = self._verify_key.encode().hex()
            self.fingerprint = self.public_key_hex[:16]
        else:
            # HMAC fallback — deterministic identity from secret
            seed = secret_seed or os.environ.get("P2P_SECRET")
            # NEW-06: Warn if no secret configured
            if not seed or seed == "changeme":
                logger.error("⚠️  CRITICAL: P2P_SECRET not configured! Node identity is insecure.")
                logger.error("   Generate one with: python3 -c 'import secrets; print(secrets.token_hex(32))'")
                logger.error("   Then set P2P_SECRET environment variable.")
                seed = seed or "changeme"
            self._fallback_secret = hashlib.sha256(f"{seed}:{name}".encode()).digest()
            self.public_key_hex = self._fallback_secret.hex()
            self.fingerprint = self.public_key_hex[:16]

    def sign(self, message: str) -> str:
        """Sign a message. Returns hex signature."""
        if HAS_NACL:
            sig = self._signing_key.sign(message.encode())
            return sig.signature.hex()
        else:
            import hmac as hmac_mod
            return hmac_mod.new(self._fallback_secret, message.encode(), hashlib.sha256).hexdigest()

    def verify(self, message: str, signature_hex: str, public_key_hex: str = None) -> bool:
        """Verify a signed message. Tries Ed25519 first; HMAC fallback uses ONLY the shared P2P secret."""
        # Try Ed25519 verification first
        if HAS_NACL and public_key_hex:
            try:
                vk = VerifyKey(bytes.fromhex(public_key_hex))
                vk.verify(message.encode(), bytes.fromhex(signature_hex))
                return True
            except BadSignatureError:
                # Ed25519 verification failed — genuine auth failure, NO fallback
                return False
            except (ValueError, TypeError):
                # Invalid key format — genuine auth failure, NO fallback
                return False

        # HMAC fallback: use ONLY the shared P2P secret, NEVER the public key
        # (the public key is public and would allow anyone to forge signatures)
        import hmac as hmac_mod
        expected = hmac_mod.new(self._fallback_secret, message.encode(), hashlib.sha256).hexdigest()
        return hmac_mod.compare_digest(expected, signature_hex)

    def challenge(self) -> Dict:
        """Generate a challenge for another node."""
        nonce = uuid.uuid4().hex
        timestamp = int(time.time())
        challenge_str = f"{self.name}:{nonce}:{timestamp}"
        return {
            "type": "auth_challenge",
            "from": self.name,
            "from_key": self.public_key_hex,
            "nonce": nonce,
            "timestamp": timestamp,
            "challenge": challenge_str,
            "signature": self.sign(challenge_str)
        }

    def respond_challenge(self, challenge: Dict) -> Dict:
        """Respond to an auth challenge."""
        challenge_str = challenge["challenge"]
        return {
            "type": "auth_response",
            "from": self.name,
            "from_key": self.public_key_hex,
            "nonce": challenge["nonce"],
            "response": self.sign(challenge_str),
            "signature": self.sign(f"{self.name}:{challenge['nonce']}")
        }

    def verify_challenge_response(self, response: Dict) -> bool:
        """Verify a challenge response from another node."""
        # Anti-replay: timestamp must be within 60s
        if abs(time.time() - response.get("timestamp", 0)) > 60:
            return False
        # Verify the signature
        challenge_str = response.get("challenge", "")
        return self.verify(challenge_str, response.get("response", ""), response.get("from_key", ""))

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "public_key": self.public_key_hex,
            "fingerprint": self.fingerprint,
            "created": self.created
        }


class WebOfTrust:
    """Decentralized trust via peer signatures.
    Nodes sign each other's public keys. Trust is transitive.
    """
    def __init__(self):
        self.trust_edges: Dict[str, Set[str]] = {}  # public_key -> set of trusted public_keys
        self.signed_by: Dict[str, Set[str]] = {}     # public_key -> set of signers

    def add_trust(self, signer_key: str, trusted_key: str):
        """Record that signer_key vouches for trusted_key."""
        if signer_key not in self.trust_edges:
            self.trust_edges[signer_key] = set()
        self.trust_edges[signer_key].add(trusted_key)
        if trusted_key not in self.signed_by:
            self.signed_by[trusted_key] = set()
        self.signed_by[trusted_key].add(signer_key)

    def trust_score(self, target_key: str, max_depth: int = 3) -> float:
        """Calculate trust score for a key based on transitive trust.
        More signers = higher trust. Direct signers count more than transitive.
        """
        direct = len(self.signed_by.get(target_key, set()))
        if direct == 0:
            return 0.0
        # Simple scoring: direct signers weighted 1.0, each hop halves
        score = direct * 1.0
        visited = {target_key}
        frontier = self.signed_by.get(target_key, set()).copy()
        depth = 1
        while frontier and depth < max_depth:
            next_frontier = set()
            for key in frontier:
                if key in visited:
                    continue
                visited.add(key)
                weight = 1.0 / (2 ** depth)
                signers = self.signed_by.get(key, set())
                score += len(signers & visited) * weight
                next_frontier |= signers
            frontier = next_frontier
            depth += 1
        return min(score, 10.0)  # Cap at 10

    def is_trusted(self, target_key: str, min_score: float = 1.0) -> bool:
        return self.trust_score(target_key) >= min_score


# ============================================================================
# FEATURE 2: RATE LIMITING
# ============================================================================

class RateLimiter:
    """Token bucket rate limiter per node."""
    def __init__(self, rate: float = 10.0, burst: int = 20):
        self.rate = rate          # tokens per second
        self.burst = burst        # max bucket size
        self._buckets: Dict[str, Dict] = {}  # node_key -> {tokens, last_refill}

    def _refill(self, key: str):
        bucket = self._buckets.setdefault(key, {"tokens": float(self.burst), "last": time.time()})
        now = time.time()
        elapsed = now - bucket["last"]
        bucket["tokens"] = min(self.burst, bucket["tokens"] + elapsed * self.rate)
        bucket["last"] = now

    def allow(self, key: str) -> bool:
        self._refill(key)
        if self._buckets[key]["tokens"] >= 1.0:
            self._buckets[key]["tokens"] -= 1.0
            return True
        return False

    def to_dict(self) -> Dict:
        return {"rate": self.rate, "burst": self.burst, "active_nodes": len(self._buckets)}


# ============================================================================
# SHARING QUOTA — Plus tu partages, plus tu peux utiliser
# ============================================================================

class SharingQuota:
    """Track contribution and enforce query quotas per peer.
    
    Score factors (from docs/SHARING_PARITY.md):
      - Models hosted: 40%
      - Chunks distributed (memory entries shared): 30%
      - Uptime: 20%
      - Reputation: 10%
    
    Score → queries/minute mapping:
      <10 → 1 q/m
      <20 → 5 q/m
      <40 → 20 q/m
      <60 → 50 q/m
      <80 → 100 q/m
      >=80 → 200 q/m
    """

    QUOTA_TIERS = [
        (10, 1),
        (20, 5),
        (40, 20),
        (60, 50),
        (80, 100),
        (float('inf'), 200),
    ]

    def __init__(self):
        # Per-peer tracking
        self._peer_stats: Dict[str, Dict] = {}
        # Per-peer token buckets (queries/minute)
        self._buckets: Dict[str, Dict] = {}

    def get_or_create(self, peer_name: str) -> Dict:
        """Get or create stats for a peer."""
        if peer_name not in self._peer_stats:
            self._peer_stats[peer_name] = {
                "models_hosted": 0,
                "chunks_distributed": 0,
                "uptime_start": time.time(),
                "reputation": 50,  # default
                "queries_served": 0,
                "queries_made": 0,
            }
        return self._peer_stats[peer_name]

    def update_models(self, peer_name: str, model_count: int):
        """Update model count for a peer."""
        stats = self.get_or_create(peer_name)
        stats["models_hosted"] = model_count

    def record_chunk(self, peer_name: str, count: int = 1):
        """Record distributed memory chunks."""
        stats = self.get_or_create(peer_name)
        stats["chunks_distributed"] += count

    def record_query_served(self, peer_name: str):
        """This peer served a query (reputation+)."""
        stats = self.get_or_create(peer_name)
        stats["queries_served"] += 1
        # Increase reputation slowly
        stats["reputation"] = min(100, stats["reputation"] + 0.1)

    def record_query_made(self, peer_name: str):
        """This peer made a query to us (consumes quota)."""
        stats = self.get_or_create(peer_name)
        stats["queries_made"] += 1

    def calculate_score(self, peer_name: str) -> float:
        """Calculate sharing score (0-100)."""
        stats = self.get_or_create(peer_name)

        # Models (40%): max 40 points
        models_score = min(stats["models_hosted"] * 8, 40)

        # Chunks (30%): max 30 points
        chunks_score = min(stats["chunks_distributed"] / 100, 30)

        # Uptime (20%): max 20 points
        uptime_hours = (time.time() - stats["uptime_start"]) / 3600
        uptime_score = min(uptime_hours / 24, 1.0) * 20

        # Reputation (10%): max 10 points
        rep_score = stats["reputation"] / 10

        total = models_score + chunks_score + uptime_score + rep_score
        return round(total, 2)

    def get_quota(self, peer_name: str) -> int:
        """Get queries/minute allowed for this peer."""
        score = self.calculate_score(peer_name)
        for threshold, quota in self.QUOTA_TIERS:
            if score < threshold:
                return quota
        return 1  # fallback

    def allow_query(self, peer_name: str) -> bool:
        """Check if a peer can make a query right now (token bucket)."""
        qpm = self.get_quota(peer_name)
        # Token bucket: 1 token = 1 query, refill at qpm/60 per second
        refill_rate = qpm / 60.0
        burst = max(qpm, 3)  # allow small burst

        if peer_name not in self._buckets:
            self._buckets[peer_name] = {"tokens": float(burst), "last": time.time()}

        bucket = self._buckets[peer_name]
        now = time.time()
        elapsed = now - bucket["last"]
        bucket["tokens"] = min(burst, bucket["tokens"] + elapsed * refill_rate)
        bucket["last"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True
        return False

    def get_peer_info(self, peer_name: str) -> Dict:
        """Get full quota info for a peer."""
        score = self.calculate_score(peer_name)
        stats = self.get_or_create(peer_name)
        return {
            "peer": peer_name,
            "score": score,
            "quota_qpm": self.get_quota(peer_name),
            "models_hosted": stats["models_hosted"],
            "chunks_distributed": stats["chunks_distributed"],
            "uptime_hours": round((time.time() - stats["uptime_start"]) / 3600, 1),
            "reputation": round(stats["reputation"], 1),
            "queries_served": stats["queries_served"],
            "queries_made": stats["queries_made"],
        }

    def to_dict(self) -> Dict:
        """Serialize all peer quotas."""
        return {name: self.get_peer_info(name) for name in self._peer_stats}


# ============================================================================
# CIRCUIT BREAKER (unchanged from v3.3, but cleaner)
# ============================================================================

class CircuitBreaker:
    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60,
                 half_open_max: int = 1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        if self.state == self.STATE_CLOSED:
            return True
        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.STATE_HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        if self.state == self.STATE_HALF_OPEN:
            if self.half_open_calls < self.half_open_max:
                self.half_open_calls += 1
                return True
            return False
        return False

    def record_success(self):
        if self.state == self.STATE_HALF_OPEN:
            self.success_count += 1
            self.state = self.STATE_CLOSED
            self.failure_count = 0
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.STATE_OPEN

    @property
    def is_available(self) -> bool:
        return self.can_execute()

    def to_dict(self) -> Dict:
        return {"state": self.state, "failures": self.failure_count,
                "last_failure": self.last_failure_time}


# ============================================================================
# FEATURE 3: CRDT-BASED MEMORY WITH VECTOR CLOCKS
# ============================================================================

class VectorClock:
    """Vector clock for ordering distributed events."""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.clocks: Dict[str, int] = {}

    def increment(self):
        self.clocks[self.node_id] = self.clocks.get(self.node_id, 0) + 1

    def merge(self, other: Dict[str, int]):
        for key, value in other.items():
            self.clocks[key] = max(self.clocks.get(key, 0), value)

    def happens_before(self, other: Dict[str, int]) -> bool:
        """Check if this clock happens-before other."""
        all_leq = True
        any_lt = False
        for key in set(list(self.clocks.keys()) + list(other.keys())):
            mine = self.clocks.get(key, 0)
            theirs = other.get(key, 0)
            if mine > theirs:
                all_leq = False
            if mine < theirs:
                any_lt = True
        return all_leq and any_lt

    def is_concurrent(self, other: Dict[str, int]) -> bool:
        return not self.happens_before(other) and not self._reverse_happens_before(other)

    def _reverse_happens_before(self, other: Dict[str, int]) -> bool:
        vc_other = VectorClock(self.node_id)
        vc_other.clocks = dict(other)
        return vc_other.happens_before(self.clocks)

    def to_dict(self) -> Dict[str, int]:
        return dict(self.clocks)

    @classmethod
    def from_dict(cls, node_id: str, data: Dict[str, int]):
        vc = cls(node_id)
        vc.clocks = dict(data)
        return vc


class CRDTMemory:
    """CRDT-based distributed memory with Last-Write-Wins.
    Uses vector clocks for ordering. Gossip protocol for propagation.
    """
    def __init__(self, node_id: str, max_size: int = 1000, default_ttl: int = 3600):
        self.node_id = node_id
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.vector_clock = VectorClock(node_id)
        self.store: Dict[str, Dict] = {}  # key -> {value, version, tombstone, metadata}

    def set(self, key: str, value: Any, ttl: int = None, author: str = None):
        """Set a value. Increments vector clock. Last-write-wins on conflict."""
        self.vector_clock.increment()
        version = self.vector_clock.to_dict()
        existing = self.store.get(key)
        # Last-write-wins: if existing has same or newer version, skip
        if existing and not self._is_newer(version, existing.get("version", {})):
            # Concurrent write — last-write-wins by timestamp
            existing_ts = existing.get("metadata", {}).get("timestamp", 0)
            new_ts = time.time()
            if new_ts <= existing_ts:
                return  # existing is newer, skip
        self.store[key] = {
            "value": value,
            "version": version,
            "tombstone": False,
            "expires": time.time() + (ttl or self.default_ttl),
            "metadata": {
                "author": author or self.node_id,
                "timestamp": time.time(),
                "node_id": self.node_id
            }
        }
        # Evict if over max_size (LRU by access time)
        while len(self.store) > self.max_size:
            oldest_key = min(self.store, key=lambda k: self.store[k]["metadata"]["timestamp"])
            del self.store[oldest_key]

    def _is_newer(self, version_a: Dict, version_b: Dict) -> bool:
        """Check if version_a is strictly newer than version_b."""
        a_greater = False
        for key in set(list(version_a.keys()) + list(version_b.keys())):
            va = version_a.get(key, 0)
            vb = version_b.get(key, 0)
            if va < vb:
                return False
            if va > vb:
                a_greater = True
        return a_greater

    def get(self, key: str) -> Any:
        entry = self.store.get(key)
        if not entry:
            return None
        if entry["tombstone"]:
            return None
        if entry["expires"] < time.time():
            del self.store[key]
            return None
        return entry["value"]

    def delete(self, key: str) -> bool:
        if key in self.store:
            self.vector_clock.increment()
            self.store[key]["tombstone"] = True
            self.store[key]["version"] = self.vector_clock.to_dict()
            self.store[key]["metadata"]["timestamp"] = time.time()
            return True
        return False

    def get_all_for_sync(self) -> Dict[str, Dict]:
        """Get all non-expired, non-tombstoned entries for P2P sync."""
        now = time.time()
        return {k: v for k, v in self.store.items()
                if not v["tombstone"] and v["expires"] > now}

    def get_delta_since(self, vector_clock: Dict[str, int]) -> Dict[str, Dict]:
        """Get entries that are newer than the given vector clock (for incremental sync)."""
        result = {}
        for key, entry in self.store.items():
            if entry["tombstone"] and entry["expires"] < time.time():
                continue
            entry_vc = entry.get("version", {})
            # Entry is newer if any component is greater
            is_newer = False
            for node, tick in entry_vc.items():
                if tick > vector_clock.get(node, 0):
                    is_newer = True
                    break
            if is_newer:
                result[key] = entry
        return result

    def merge_from_sync(self, data: Dict[str, Dict]) -> int:
        """Merge entries from a P2P sync. Returns count of merged entries.
        MED-04: Validates key length, value size, and TTL before merging.
        NEW-04: Rejects sync with too many entries.
        """
        if len(data) > MAX_SYNC_ENTRIES:
            logger.warning(f"Rejecting sync: too many entries ({len(data)} > {MAX_SYNC_ENTRIES})")
            return 0
        merged = 0
        for key, entry in data.items():
            # MED-04: Validate key length
            if len(key) > MAX_KEY_LENGTH:
                continue
            # MED-04: Validate value size
            val = entry.get("value")
            if val is not None and len(json.dumps(val)) > MAX_VALUE_SIZE:
                continue
            # MED-04: Cap TTL
            if entry.get("ttl") and entry["ttl"] > MAX_TTL:
                entry["ttl"] = MAX_TTL
            existing = self.store.get(key)
            if not existing:
                self.store[key] = entry
                self.vector_clock.merge(entry.get("version", {}))
                merged += 1
            else:
                # Last-write-wins by timestamp
                existing_ts = existing.get("metadata", {}).get("timestamp", 0)
                new_ts = entry.get("metadata", {}).get("timestamp", 0)
                if new_ts > existing_ts:
                    self.store[key] = entry
                    self.vector_clock.merge(entry.get("version", {}))
                    merged += 1
                elif new_ts == existing_ts:
                    # Same timestamp: deterministic tiebreak by node_id
                    if entry.get("metadata", {}).get("node_id", "") > existing.get("metadata", {}).get("node_id", ""):
                        self.store[key] = entry
                        self.vector_clock.merge(entry.get("version", {}))
                        merged += 1
        return merged

    def stats(self) -> Dict:
        active = sum(1 for v in self.store.values() if not v["tombstone"] and v["expires"] > time.time())
        return {
            "total_entries": len(self.store),
            "active_entries": active,
            "vector_clock": self.vector_clock.to_dict()
        }


# ============================================================================
# PEER DISCOVERY
# ============================================================================

class PeerDiscovery:
    """Dynamic peer discovery: Tailscale, mDNS, config fallback, peer referral."""

    def __init__(self, node_name: str, own_host: str, own_port: int,
                 config_peers: List[Dict] = None):
        self.node_name = node_name
        self.own_host = own_host
        self.own_port = own_port
        self.known_peers: Dict[str, Dict] = {}
        self.config_peers = config_peers or []
        self.last_discovery = 0
        self.discovery_interval = 300

    def _get_broadcast_subnets(self) -> List[str]:
        """Detect broadcast subnets automatically."""
        subnets = []
        try:
            import socket
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                addr = info[4][0]
                if addr and not addr.startswith('127.'):
                    # Derive broadcast from IP
                    parts = addr.split('.')
                    subnets.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
            # Deduplicate
            subnets = list(dict.fromkeys(subnets))
        except Exception:
            pass
        if not subnets:
            subnets = ['255.255.255.255']  # Broadcast to all
        return subnets

    async def discover_all(self) -> List[Dict]:
        found = {}
        for p in self.config_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            found[key] = p

        ts_peers = await self._discover_tailscale()
        for p in ts_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            if key not in found:
                found[key] = p

        mdns_peers = await self._discover_mdns()
        for p in mdns_peers:
            key = f"{p['host']}:{p.get('port', 8081)}"
            if key not in found:
                found[key] = p

        self.known_peers = found
        self.last_discovery = time.time()
        if found:
            logger.info(f"Discovery: found {len(found)} potential peers")
        return list(found.values())

    async def _discover_tailscale(self) -> List[Dict]:
        peers = []
        try:
            proc = await asyncio.create_subprocess_exec(
                'tailscale', 'status', '--json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0:
                status = json.loads(stdout)
                for peer in status.get('Peer', {}).values():
                    if peer.get('Online', False):
                        ips = peer.get('TailscaleIPs', [])
                        if peer.get('HostName') == self.node_name:
                            continue
                        own_ts_ip = status.get('Self', {}).get('TailscaleIPs', [])
                        if own_ts_ip and any(ip in own_ts_ip for ip in ips):
                            continue
                        # Bug #5 fix: skip if same IP as a config peer but different port (duplicate)
                        # Also skip if IP matches our own Tailscale IP
                        is_dup = False
                        for cp in self.config_peers:
                            if ips and ips[0] == cp.get('host') and 8081 != cp.get('port', 8080):
                                is_dup = True
                                break
                        if is_dup:
                            continue
                        if ips:
                            peers.append({
                                'name': peer.get('HostName', 'unknown'),
                                'host': ips[0],
                                'port': 8081,
                                'source': 'tailscale'
                            })
        except (OSError, json.JSONDecodeError, asyncio.TimeoutError):
            pass
        return peers

    async def _discover_mdns(self) -> List[Dict]:
        """Simple UDP broadcast for local network discovery."""
        peers = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2)
            msg = json.dumps({
                'type': 'pinkybrain_discovery',
                'node': self.node_name,
                'port': self.own_port
            }).encode()
            for subnet in self._get_broadcast_subnets():
                try:
                    sock.sendto(msg, (subnet, 8090))
                except OSError:
                    pass
            sock.close()
        except OSError:
            pass
        return peers


# ============================================================================
# LOAD BALANCER
# ============================================================================

class LoadBalancer:
    """Route queries based on latency, model availability, success rate, CB state."""

    def __init__(self):
        self.node_scores: Dict[str, float] = {}

    def calculate_score(self, peer, model: str = None) -> float:
        if peer.latency == float('inf') or not peer.available:
            return float('inf')
        latency_score = min(peer.latency / 10, 100)
        model_penalty = 0
        if model and model not in peer.models and peer.models:
            model_penalty = 50
        success_score = 100 - (peer.success_rate * 100)
        cb_penalty = 0
        if peer.circuit_breaker.state != CircuitBreaker.STATE_CLOSED:
            cb_penalty = 100
        return (latency_score * 0.4) + (model_penalty * 0.3) + (success_score * 0.2) + (cb_penalty * 0.1)

    def select_best_peer(self, peers: list, model: str = None) -> Optional[Any]:
        if not peers:
            return None
        best = None
        best_score = float('inf')
        for peer in peers:
            if not peer.circuit_breaker.can_execute():
                continue
            score = self.calculate_score(peer, model)
            if score < best_score:
                best_score = score
                best = peer
        return best

    def should_handle_locally(self, local_cpu: float, local_mem_pct: float,
                               peer_count: int) -> bool:
        if peer_count == 0:
            return True
        if local_cpu < 50 and local_mem_pct < 70:
            return True
        return False


# ============================================================================
# PEER
# ============================================================================

class Peer:
    def __init__(self, name: str, host: str, port: int, models: List[str],
                 public_key_hex: str = None):
        self.name = name
        self.host = host
        self.port = port
        self.models = models
        self.public_key_hex = public_key_hex or ""
        self.available = True
        self.latency = float('inf')
        self.success_rate = 1.0
        self.circuit_breaker = CircuitBreaker()
        self.last_seen = 0
        self.model_stats: Dict[str, Dict] = {}

    async def ping(self, session: aiohttp.ClientSession, auth_headers: Dict = None) -> float:
        start = time.time()
        try:
            headers = auth_headers or {}
            async with session.get(
                f'http://{self.host}:{self.port}/api/ping',
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    self.latency = (time.time() - start) * 1000
                    self.available = True
                    self.last_seen = time.time()
                    self.circuit_breaker.record_success()
                    return self.latency
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            pass
        self.available = False
        self.circuit_breaker.record_failure()
        self.latency = float('inf')
        return float('inf')

    def _update_stats(self, model: str, success: bool, latency: float):
        if model not in self.model_stats:
            self.model_stats[model] = {"queries": 0, "success": 0, "avg_latency": 0}
        stats = self.model_stats[model]
        stats["queries"] += 1
        if success:
            stats["success"] += 1
        stats["avg_latency"] = (stats["avg_latency"] * (stats["queries"] - 1) + latency) / stats["queries"]

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "host": self.host, "port": self.port,
            "models": self.models, "available": self.available,
            "latency": round(self.latency, 1), "public_key": self.public_key_hex,
            "circuit_breaker": self.circuit_breaker.to_dict()
        }


# ============================================================================
# MODEL ROUTING
# ============================================================================

# ========================================================================
# MULTI-LLM PROVIDER ADAPTERS
# ========================================================================

class ProviderAdapter:
    """Base class for LLM providers. Each adapter knows how to query its API."""
    provider_type: str = "base"

    def __init__(self, name: str, config: Dict):
        self.name = name
        self.enabled = config.get("enabled", True)
        self.models = config.get("models", [])

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        raise NotImplementedError

    def supports(self, model: str) -> bool:
        if not self.models:
            return True  # Empty models list = supports all
        return model in self.models or model.startswith(tuple(self.models))


class OllamaProvider(ProviderAdapter):
    """Ollama API provider (default, backward compatible)."""
    provider_type = "ollama"

    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 11434)
        self.base_url = f"http://{self.host}:{self.port}"

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        try:
            async with session.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "response": data.get("response", ""),
                        "model": model,
                        "source": f"ollama:{self.name}",
                        "tokens_used": data.get("eval_count", 0)
                    }
                return {"response": "", "model": model, "source": f"ollama:{self.name}",
                        "error": f"Ollama {self.name}: HTTP {resp.status}"}
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            return {"response": "", "model": model, "source": f"ollama:{self.name}", "error": str(e)}


class OpenAIProvider(ProviderAdapter):
    """OpenAI Chat Completions API provider. Also works for any OpenAI-compatible API."""
    provider_type = "openai"

    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        try:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    return {
                        "response": content,
                        "model": model,
                        "source": f"openai:{self.name}",
                        "tokens_used": usage.get("total_tokens", 0)
                    }
                text = await resp.text()
                return {"response": "", "model": model, "source": f"openai:{self.name}",
                        "error": f"OpenAI {self.name}: HTTP {resp.status} {text[:200]}"}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return {"response": "", "model": model, "source": f"openai:{self.name}", "error": str(e)}


class AnthropicProvider(ProviderAdapter):
    """Anthropic Messages API provider."""
    provider_type = "anthropic"

    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://api.anthropic.com").rstrip("/")

    async def query(self, session: aiohttp.ClientSession, model: str, prompt: str, timeout: int = 120) -> Dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            async with session.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("content", [{}])
                    text = content[0].get("text", "") if content else ""
                    usage = data.get("usage", {})
                    return {
                        "response": text,
                        "model": model,
                        "source": f"anthropic:{self.name}",
                        "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    }
                text = await resp.text()
                return {"response": "", "model": model, "source": f"anthropic:{self.name}",
                        "error": f"Anthropic {self.name}: HTTP {resp.status} {text[:200]}"}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return {"response": "", "model": model, "source": f"anthropic:{self.name}", "error": str(e)}


class OpenAICompatibleProvider(OpenAIProvider):
    """Alias for OpenAI provider — works with any OpenAI-compatible endpoint (LM Studio, vLLM, etc.)."""
    provider_type = "openai_compatible"


PROVIDER_TYPES = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


class ModelRouter:
    CODE_KEYWORDS = ['code', 'program', 'script', 'debug', 'implement', 'class ', 'def ', 'async ']
    REASONING_KEYWORDS = ['explain', 'why', 'how does', 'analyze', 'compare', 'what if']
    CREATIVE_KEYWORDS = ['write', 'story', 'poem', 'creative', 'imagine', 'design']

    def __init__(self, negotiator: 'ModelNegotiator' = None):
        self.negotiator = negotiator

    def route(self, prompt: str, available_models: List[str]) -> str:
        p = prompt.lower()
        if any(kw in p for kw in self.CODE_KEYWORDS):
            for m in available_models:
                if 'coder' in m or 'code' in m or 'deepseek' in m:
                    return m
        if any(kw in p for kw in self.REASONING_KEYWORDS):
            for m in available_models:
                if 'reason' in m or 'think' in m or 'qwen' in m:
                    return m
        if available_models:
            return available_models[0]
        return "glm-5.1:cloud"

    def route_with_capabilities(self, model: str, available_models: List[str],
                                peers: List[Any] = None) -> Dict:
        """Route considering GPU/CPU capabilities.
        
        Returns: {'model': str, 'target': str, 'reason': str}
        target can be 'local', peer name, or 'cloud'
        """
        if self.negotiator:
            target = self.negotiator.select_best_node(model, peers or [])
            if target:
                return {'model': model, 'target': target, 'reason': f'capabilities_routing -> {target}'}
        # Fallback to local
        return {'model': model, 'target': 'local', 'reason': 'no_negotiator_fallback'}

    def get_fallback(self, model: str, available_models: List[str]) -> Optional[str]:
        if model in available_models:
            return model
        if available_models:
            return available_models[0]
        return None


# ============================================================================
# ENSEMBLE CONSENSUS
# ============================================================================

class EnsembleConsensus:
    def __init__(self, agreement_threshold: float = 0.6):
        self.agreement_threshold = agreement_threshold

    async def query_ensemble(self, session: aiohttp.ClientSession,
                              peers: list, prompt: str, model: str = None) -> Dict:
        results = []
        for peer in peers:
            if peer.available and peer.circuit_breaker.can_execute():
                try:
                    async with session.post(
                        f'http://{peer.host}:{peer.port}/api/query',
                        json={"prompt": prompt, "model": model},
                        timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results.append(data.get("response", ""))
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass
        if not results:
            return {"response": "", "consensus": 0, "sources": 0}
        # Simple consensus: most common response wins
        from collections import Counter
        counter = Counter(r[:200] for r in results)
        best, count = counter.most_common(1)[0]
        consensus = count / len(results) if results else 0
        # Return the full response that matches the best prefix
        for r in results:
            if r[:200] == best:
                return {"response": r, "consensus": consensus, "sources": len(results)}
        return {"response": results[0], "consensus": consensus, "sources": len(results)}


# ============================================================================
# QUERY HISTORY
# ============================================================================

class QueryHistory:
    def __init__(self, max_entries: int = 1000):
        self._entries: deque = deque(maxlen=max_entries)

    async def add(self, query: Dict):
        self._entries.append({**query, "timestamp": time.time()})

    async def get(self, limit: int = 10) -> List[Dict]:
        return list(self._entries)[-limit:]


# ============================================================================
# CONFIG LOADER
# ============================================================================

def load_config(config_path: str = None) -> Dict:
    """Load config from JSON file or defaults.
    
    P2P_SECRET priority: environment variable > config file > default.
    A warning is logged if the secret is missing or weak.
    """
    default_config = {
        "node_name": "unknown",
        "version": "5.2.0",
        "host": "0.0.0.0",
        "port": 8080,
        "ollama_host": "127.0.0.1",
        "ollama_port": 11434,
        "local_models": ["glm-5.1:cloud"],
        "providers": {},
        "heartbeat_interval": 30,
        "auto_heal_interval": 120,
        "memory_max_size": 1000,
        "memory_default_ttl": 3600,
        "p2p_secret": "changeme-configure-in-config",  # overridden by env var
        "tailscale_auto_discovery": True,
        "circuit_breaker": {
            "failure_threshold": 3,
            "recovery_timeout": 60,
            "half_open_max_calls": 1
        },
        "token_lifetime": 86400,
        "token_rotation_interval": 3600,
        "discovery_interval": 300,
        "stealth_mode": False,
        "share_ai": False,
        "model_networks": {
            "private_networks": [
                {"id": 1, "name": "Réseau Principal", "secret": ""}
            ],
            "model_permissions": {}
        },
        "rate_limit": 10.0,
        "rate_burst": 20,
        "peers": [],
        "seed_nodes": []
    }

    if config_path and Path(config_path).exists():
        try:
            with open(config_path) as f:
                user_config = json.load(f)
            for key, value in user_config.items():
                default_config[key] = value
            logger.info(f"Config loaded from {config_path}")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Config load failed, using defaults: {e}")

    # CRIT-01 fix: Environment variable takes priority over config file
    env_secret = os.environ.get("P2P_SECRET")
    if env_secret:
        default_config["p2p_secret"] = env_secret
        logger.info("P2P_SECRET loaded from environment variable")

    # Warn if secret is weak or default
    secret = default_config.get("p2p_secret", "")
    WEAK_SECRETS = {
        "changeme-configure-in-config", "changeme", "password", "secret",
        "p2p_secret", "default", "test", "",
    }
    if secret in WEAK_SECRETS or len(secret) < 16:
        logger.warning(
            "⚠️  P2P_SECRET is weak or default! Generate a strong secret with:\n"
            "   python3 -c 'import secrets; print(secrets.token_hex(32))'\n"
            "   Then set it via P2P_SECRET environment variable or config file.\n"
            "   DO NOT commit secrets to version control!"
        )

    return default_config


# ============================================================================
# PINKYBRAIN v5.2 MAIN
# ============================================================================

class PinkyBrain:
    """PinkyBrain v5.2 — P2P Distributed AI Network"""

    def __init__(self, config: Dict):
        self.config = config
        self.node_name = config["node_name"]
        self.version = "5.2.0"
        self.host = config["host"]
        self.port = config["port"]
        self.ollama_host = config["ollama_host"]
        self.ollama_port = config["ollama_port"]
        self.local_models = config["local_models"]
        self.p2p_secret = os.environ.get("P2P_SECRET") or config.get("p2p_secret")
        if not self.p2p_secret:
            logger.error("⚠️  P2P_SECRET not configured! Set P2P_SECRET env var or p2p_secret in config.")
            logger.error("⚠️  Generate one with: python3 -c 'import secrets; print(secrets.token_hex(32))'")
            self.p2p_secret = os.environ.get("P2P_SECRET", "changeme-configure-in-config")
        elif self.p2p_secret in ("changeme", "changeme-configure-in-config"):
            logger.warning("⚠️  P2P_SECRET is a known default — please change it!")
        self.stealth_mode = config.get("stealth_mode", False)
        self.share_ai = config.get("share_ai", False)
        # v5.2: Model networks — fine-grained model sharing permissions
        self.model_networks = config.get("model_networks", {
            "private_networks": [{"id": 1, "name": "Réseau Principal", "secret": ""}],
            "model_permissions": {}
        })
        # Multi-LLM providers
        self.providers: Dict[str, ProviderAdapter] = {}
        self._model_provider_map: Dict[str, str] = {}  # model_name -> provider_name
        self._init_providers(config)

        # Node Identity (Ed25519 or HMAC fallback)
        self.identity = NodeIdentity(self.node_name, self.p2p_secret)

        # Web of Trust
        self.web_of_trust = WebOfTrust()

        # Rate Limiter
        self.rate_limiter = RateLimiter(
            rate=config.get("rate_limit", 10.0),
            burst=config.get("rate_burst", 20)
        )
        # HIGH-04: Global rate limiter for ALL endpoints (separate from auth rate limiter)
        self._global_rate_limiter = RateLimiter(
            rate=GLOBAL_RATE_LIMIT_RATE,
            burst=GLOBAL_RATE_LIMIT_BURST
        )
        # MED-05 + NEW-01: Nonce anti-replay tracking (set + threading.Lock)
        self._used_nonces: Set[str] = set()
        self._nonce_timestamps: Dict[str, float] = {}
        self._nonce_lock = threading.Lock()
        # MED-07: Persistent token blacklist
        self._token_blacklist_file = Path.home() / ".pinkybrain" / "token_blacklist.json"
        self._token_blacklist: Set[str] = set()
        self._token_blacklist_lock = threading.Lock()
        self._load_token_blacklist()
        self.sharing_quota = SharingQuota()  # query quotas per peer

        # New capabilities
        self.own_capabilities = NodeCapabilities()
        logger.info(f"🖥️ Node capabilities: GPU={self.own_capabilities.gpu_available} "
                    f"({self.own_capabilities.gpu_name or 'none'}), "
                    f"max_model={self.own_capabilities.max_model_category}")
        self.model_negotiator = ModelNegotiator(self.own_capabilities)
        self.zero_config = ZeroConfigDiscovery(
            node_name=self.node_name,
            own_port=self.port,
            capabilities=self.own_capabilities.to_dict()
        )
        self.gamified_score = GamifiedScore()
        self.auto_updater = AutoUpdater(auto_install=config.get('auto_update', False))
        self.systray = SystrayDaemon(node_name=self.node_name)

        # ====================================================================
        # Core modules
        # ====================================================================

        # Resource Guard — protects local user from mesh overload
        if HAS_RESOURCE_GUARD:
            mesh_config = config.get("public_mesh", {})
            rg_config = {
                "max_cpu_percent": mesh_config.get("max_cpu_percent", 30),
                "max_ram_share_mb": mesh_config.get("max_ram_share_mb", 2048),
                "gpu_share": mesh_config.get("gpu_share", False),
                "priority": mesh_config.get("priority", "local_first"),
                "bandwidth_limit_kbps": mesh_config.get("bandwidth_limit_kbps", 5000),
                "enabled": mesh_config.get("enabled", False),
            }
            self.resource_guard = ResourceGuard(config=rg_config)
            logger.info(f"🛡️ Resource Guard: {self.resource_guard._state.value}")
        else:
            self.resource_guard = None

        # Bandwidth Quota — monthly data and bandwidth limits like a mobile plan
        if HAS_BANDWIDTH_QUOTA:
            bw_config = config.get("bandwidth_quota", {})
            # Merge mesh bandwidth_limit_kbps into quota config
            if "bandwidth_limit_kbps" not in bw_config:
                bw_config["bandwidth_limit_kbps"] = mesh_config.get("bandwidth_limit_kbps", 5000)
            self.bandwidth_quota = BandwidthQuota(config=bw_config)
            logger.info(f"📡 Bandwidth Quota: {self.bandwidth_quota.monthly_data_gb} GB/{self.bandwidth_quota.period.value}, "
                        f"{self.bandwidth_quota.bandwidth_limit_kbps} kbps max")
        else:
            self.bandwidth_quota = None

        # Credit System — mesh economics (earn by sharing, spend by querying)
        if HAS_CREDIT_SYSTEM:
            credit_config = config.get("credit_system", {})
            self.credit_system = CreditSystem(config=credit_config)
            self.credit_system.set_sharing_quota(self.sharing_quota)
            self.credit_system.set_bandwidth_quota(self.bandwidth_quota)
            logger.info(
                f"💰 Credit System: base={self.credit_system.base_allocation}/mois, "
                f"max={self.credit_system.max_balance}, "
                f"carry={self.credit_system.carry_over_pct*100}%"
            )
        else:
            self.credit_system = None

        # Adaptive Scheduler — chooses strategy based on peer count
        if HAS_ADAPTIVE_SCHEDULER:
            self.adaptive_scheduler = AdaptiveScheduler(
                identity=self.identity,
                resource_guard=self.resource_guard,
                tracker_client=None,  # tracker_client set later,
                config={"prefer_local": True}
            )
            logger.info(f"🧠 Adaptive Scheduler: strategy={self.adaptive_scheduler._strategy.value}")
        else:
            self.adaptive_scheduler = None

        # Conversation Store — persistent conversations with privacy levels
        conv_config = config.get("conversation_store", {})
        if HAS_CONVERSATION_STORE and conv_config.get("enabled", True):
            self.conversation_store = ConversationStore(
                conversations_dir=os.path.expanduser(conv_config.get("storage_dir", "~/.pinkybrain/conversations")),
                encryption_password=None  # Encryption configured separately
            )
            logger.info(f"💾 Conversation Store: enabled ({conv_config.get('storage_dir', '~/.pinkybrain/conversations')})")
        else:
            self.conversation_store = None

        # Model Share Manager — secure bridge for sharing models
        if HAS_MODEL_SHARE_MANAGER:
            base_dir = os.path.expanduser(config.get("base_dir", "~/.pinkybrain"))
            self.model_share_manager = ModelShareManager(base_dir=base_dir)
            logger.info(f"📂 Model Share Manager: ready ({base_dir}/shared_models/)")
        else:
            self.model_share_manager = None

        # Tracker Client — public mesh discovery
        tracker_config = config.get("public_mesh", {})
        if HAS_TRACKER_CLIENT and tracker_config.get("enabled", False):
            self.tracker_client = TrackerClient(
                identity=self.identity,
                config=tracker_config
            )
            logger.info(f"🌐 Tracker Client: {len(tracker_config.get('tracker_url', [])) if isinstance(tracker_config.get('tracker_url'), list) else 1} tracker(s)")
        else:
            self.tracker_client = None

        # Components
        self.router = ModelRouter(negotiator=self.model_negotiator)
        self.ensemble = EnsembleConsensus()
        self.history = QueryHistory()

        # Specialist Router — multi-LLM specialty-based routing
        if HAS_MODEL_SPECIALIST:
            specialist_config = config.get("specialist", {})
            self.specialist_router = SpecialistRouter(config=specialist_config)
            self.specialist_router.set_available_models(self.local_models)
            # Multi-model executor (query_fn set at runtime when session available)
            self.multi_model_executor = MultiModelExecutor(config=specialist_config)
            logger.info(f"🎯 Specialist Router: {len(self.specialist_router._profiles)} profiles, "
                        f"{len(self.local_models)} available models")
        else:
            self.specialist_router = None
            self.multi_model_executor = None

        # v5.2.0: Model Registry — catalogue de modèles avec métadonnées riches
        if HAS_MODEL_REGISTRY:
            self.model_registry = ModelRegistry(base_dir=base_dir)
            try:
                self.model_registry.initialize()
                logger.info(f"📚 Model Registry: {len(self.model_registry._cards)} models in catalog")
            except Exception as e:
                logger.warning(f"Model Registry init failed: {e}")
                self.model_registry = None
        else:
            self.model_registry = None

        # v5.2.0: Network Sync — DNS dynamique + sync catalogue mesh
        if HAS_NETWORK_SYNC:
            self.network_sync = NetworkSync(
                model_registry=self.model_registry,
                tracker_client=None,  # Sera branché plus tard avec self.tracker_client
                persist_dir=str(Path.home() / ".pinkybrain"),
            )
            logger.info("🔄 NetworkSync initialized")
        else:
            self.network_sync = None

    def _init_providers(self, config: Dict):
        """Initialize LLM providers from config. Falls back to Ollama-only if no providers."""
        providers_config = config.get("providers", {})

        if providers_config:
            # Multi-provider mode
            for name, pconf in providers_config.items():
                ptype = pconf.get("type", "ollama")
                if not pconf.get("enabled", True):
                    logger.info(f"Provider '{name}' disabled, skipping")
                    continue
                cls = PROVIDER_TYPES.get(ptype, OllamaProvider)
                provider = cls(name, pconf)
                self.providers[name] = provider
                # Map models to provider
                for model in provider.models:
                    self._model_provider_map[model] = name
                logger.info(f"Provider '{name}' ({ptype}): {len(provider.models)} models "
                            f"- {', '.join(provider.models[:3])}{'...' if len(provider.models) > 3 else ''}")
        else:
            # Backward compat: create default Ollama provider from legacy config
            ollama_conf = {
                "type": "ollama",
                "host": config.get("ollama_host", "127.0.0.1"),
                "port": config.get("ollama_port", 11434),
                "models": config.get("local_models", ["glm-5.1:cloud"]),
                "enabled": True
            }
            self.providers["ollama"] = OllamaProvider("ollama", ollama_conf)
            for model in self.local_models:
                self._model_provider_map[model] = "ollama"
            logger.info(f"No providers configured, using Ollama at {self.ollama_host}:{self.ollama_port}")

        # Build complete local_models list from all providers
        all_models = set(self.local_models) if self.local_models else set()
        for provider in self.providers.values():
            all_models.update(provider.models)
        self.local_models = list(all_models)
        logger.info(f"Available models ({len(self.local_models)}): {', '.join(sorted(self.local_models)[:5])}{'...' if len(self.local_models) > 5 else ''}")

        # CRDT Memory
        self.memory = CRDTMemory(
            node_id=self.node_name,
            max_size=config.get("memory_max_size", 1000),
            default_ttl=config.get("memory_default_ttl", 3600)
        )

        # Discovery
        self.discovery = PeerDiscovery(
            node_name=self.node_name,
            own_host=self.host,
            own_port=self.port,
            config_peers=config.get("peers", [])
        )

        # Load Balancer
        self.load_balancer = LoadBalancer()

        # Peers
        self.peers: List[Peer] = []

        # Stats
        self.queries = 0
        self.successful = 0
        self.start_time = time.time()

        # Brain LLM (async, non-blocking, cloud on demand)
        try:
            from brain_llm import BrainLLM
            self.brain_llm = BrainLLM(node_name=self.node_name)
        except ImportError:
            self.brain_llm = None
            logger.info("brain_llm not available (optional)")

        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None

        # Heartbeat
        self.heartbeat_interval = config.get("heartbeat_interval", 30)
        self.heartbeat_running = False

        # WebSocket clients
        self.ws_clients: Dict[str, web.WebSocketResponse] = {}  # id -> ws
        self.ws_authenticated: Set[str] = set()  # authenticated ws client ids

        # Gossip protocol state
        self._gossip_seen: Set[str] = set()  # message IDs already seen
        self._gossip_queue: deque = deque(maxlen=200)  # pending gossip messages

        # Event log
        self.event_log: deque = deque(maxlen=50)

    def _check_and_add_nonce(self, nonce: str) -> bool:
        """NEW-01: Thread-safe nonce check and add. Returns True if nonce is new."""
        with self._nonce_lock:
            now = time.time()
            # Cleanup expired nonces when set is getting large
            if len(self._used_nonces) > MAX_NONCE_CACHE // 2:
                expired = [k for k, v in self._nonce_timestamps.items() if now - v > HMAC_WINDOW_SECONDS + 10]
                for k in expired:
                    self._used_nonces.discard(k)
                    del self._nonce_timestamps[k]
            if nonce in self._used_nonces:
                return False
            self._used_nonces.add(nonce)
            self._nonce_timestamps[nonce] = now
            return True

    def _load_token_blacklist(self):
        """MED-07: Load token blacklist from disk."""
        try:
            if self._token_blacklist_file.exists():
                with open(self._token_blacklist_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._token_blacklist = set(data.get("blacklist", []))
                    elif isinstance(data, list):
                        self._token_blacklist = set(data)
        except (OSError, json.JSONDecodeError):
            self._token_blacklist = set()

    def _save_token_blacklist(self):
        """MED-07: Save token blacklist to disk."""
        try:
            self._token_blacklist_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._token_blacklist_file, 'w') as f:
                json.dump({"blacklist": list(self._token_blacklist)}, f)
            # LOW-02: Restrict permissions
            self._token_blacklist_file.chmod(0o600)
        except OSError:
            pass

    def _is_token_blacklisted(self, token_id: str) -> bool:
        """Check if a token is blacklisted."""
        with self._token_blacklist_lock:
            return token_id in self._token_blacklist

    def _blacklist_token(self, token_id: str):
        """Add a token to the blacklist."""
        with self._token_blacklist_lock:
            self._token_blacklist.add(token_id)
            self._save_token_blacklist()

    def log_event(self, event_type: str, message: str, level: str = "info"):
        entry = {
            "time": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "level": level
        }
        self.event_log.append(entry)
        try:
            log_file = Path(__file__).parent.parent / "logs" / "events.jsonl"
            log_file.parent.mkdir(exist_ok=True)
            # LOW-01: Restrict log file permissions
            if not log_file.exists():
                log_file.touch(mode=0o600)
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except OSError:
            pass

    async def add_peer(self, peer: Peer):
        if peer.host in (self.host, '127.0.0.1', 'localhost') and peer.port == self.port:
            return
        # Skip duplicates
        for p in self.peers:
            if p.host == peer.host and p.port == peer.port:
                return
        self.peers.append(peer)
        self.log_event("peer_added", f"Peer {peer.name} added ({peer.host}:{peer.port})")

    def purge_dead_peers(self):
        """Remove peers with open circuit breaker and stale last_seen."""
        cutoff = time.time() - 600  # 10 min
        before = len(self.peers)
        self.peers = [p for p in self.peers
                      if p.circuit_breaker.state != CircuitBreaker.STATE_OPEN
                      or p.last_seen > cutoff]
        removed = before - len(self.peers)
        if removed:
            logger.info(f"Purged {removed} dead peers")

    async def initialize(self):
        self.session = aiohttp.ClientSession()
        self.heartbeat_running = True

        # Discover peers
        found_peers = await self.discovery.discover_all()
        for peer_info in found_peers:
            peer = Peer(
                name=peer_info.get('name', 'unknown'),
                host=peer_info['host'],
                port=peer_info.get('port', 8081),
                models=peer_info.get('models', []),
                public_key_hex=peer_info.get('public_key', '')
            )
            await self.add_peer(peer)
            # Update sharing quota model count
            self.sharing_quota.update_models(peer.name, len(peer.models))

        # Ping all peers
        if self.peers:
            tasks = [p.ping(self.session) for p in self.peers]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Start brain_llm if available
        if self.brain_llm:
            try:
                await self.brain_llm.start()
            except Exception as e:
                logger.warning(f"brain_llm start failed: {e}")

        self.log_event("init", f"PinkyBrain v{self.version} initialized as '{self.node_name}'")

        # Start Resource Guard background monitor
        if self.resource_guard:
            await self.resource_guard.start()
            logger.info(f"🛡️ Resource Guard started: {self.resource_guard._state.value}")

        # Start Tracker Client if enabled
        if self.tracker_client:
            try:
                await self.tracker_client.start()
                logger.info(f"🌐 Tracker Client started")
            except Exception as e:
                logger.warning(f"Tracker Client start failed: {e}")
                self.tracker_client = None

        # Brancher NetworkSync avec le tracker_client
        if self.network_sync:
            self.network_sync.tracker_client = self.tracker_client
            # Lancer la sync périodique en arrière-plan
            asyncio.create_task(self.network_sync.start())
            logger.info("🔄 NetworkSync background sync started")

    async def check_peers(self):
        if not self.session:
            return
        for peer in self.peers:
            await peer.ping(self.session)
        self.purge_dead_peers()

    async def start_heartbeat(self):
        while self.heartbeat_running:
            await asyncio.sleep(self.heartbeat_interval)
            await self.check_peers()

    async def query(self, prompt: str, model: str = None,
                    strategy: str = "auto") -> Dict:
        start = time.time()
        self.queries += 1
        result = {"response": "", "model": model or "auto", "latency_ms": 0, "source": "local"}

        # Check if should handle locally
        local_cpu = psutil.cpu_percent(interval=0.1) if HAS_PSUTIL else 0
        local_mem = psutil.virtual_memory() if HAS_PSUTIL else None

        if strategy == "consensus":
            consensus = await self.ensemble.query_ensemble(
                self.session, self.peers, prompt, model)
            result["response"] = consensus.get("response", "")
            result["source"] = f"consensus:{consensus.get('sources', 0)}"
            result["consensus"] = consensus.get("consensus", 0)
        elif (strategy == "auto" and self.peers and
              not self.load_balancer.should_handle_locally(local_cpu, local_mem.percent, len(self.peers))):
            best = self.load_balancer.select_best_peer(self.peers, model)
            if best:
                result = await self._query_peer(best, prompt, model)
                if not result.get("response"):
                    result = await self._query_local(model, prompt)
            else:
                result = await self._query_local(model, prompt)
        else:
            result = await self._query_local(model, prompt)

        result["latency_ms"] = round((time.time() - start) * 1000, 1)
        if result.get("response"):
            self.successful += 1
        await self.history.add({"prompt": prompt[:100], "model": result.get("model", ""),
                                 "latency_ms": result["latency_ms"], "source": result.get("source", "")})
        return result

    async def _query_local(self, model: str, prompt: str) -> Dict:
        target = model or self.router.route(prompt, self.local_models)
        # Route to the correct provider
        provider_name = self._model_provider_map.get(target)
        if provider_name and provider_name in self.providers:
            provider = self.providers[provider_name]
            result = await provider.query(self.session, target, prompt)
            if not result.get("source"):
                result["source"] = f"provider:{provider_name}"
            return result
        # Fallback: try Ollama directly if model not in any provider
        try:
            async with self.session.post(
                f'http://{self.ollama_host}:{self.ollama_port}/api/generate',
                json={"model": target, "prompt": prompt, "stream": False},
                timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"response": data.get("response", ""), "model": target,
                            "source": "local", "tokens_used": data.get("eval_count", 0)}
                return {"response": "", "model": target, "source": "local",
                        "error": f"Ollama: {resp.status}"}
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            return {"response": "", "model": target, "source": "local", "error": str(e)}

    async def _query_peer(self, peer: Peer, prompt: str, model: str = None) -> Dict:
        try:
            path = "/api/query"
            headers = self._auth_headers(path=path)
            async with self.session.post(
                f'http://{peer.host}:{peer.port}{path}',
                json={"prompt": prompt, "model": model},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    peer._update_stats(model or "auto", True, 0)
                    return data
                peer._update_stats(model or "auto", False, 0)
                return {"response": "", "source": f"peer:{peer.name}", "error": f"Peer: {resp.status}"}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            peer._update_stats(model or "auto", False, 0)
            return {"response": "", "source": f"peer:{peer.name}", "error": str(e)}

    def get_status(self) -> Dict:
        uptime = time.time() - self.start_time
        # Build provider info
        providers_info = {}
        for name, provider in self.providers.items():
            providers_info[name] = {
                "type": provider.provider_type,
                "models": provider.models,
                "enabled": provider.enabled
            }
            if isinstance(provider, OllamaProvider):
                providers_info[name]["host"] = provider.host
                providers_info[name]["port"] = provider.port
            elif isinstance(provider, (OpenAIProvider, OpenAICompatibleProvider)):
                providers_info[name]["base_url"] = provider.base_url
            elif isinstance(provider, AnthropicProvider):
                providers_info[name]["base_url"] = provider.base_url
        return {
            "node": self.node_name,
            "version": self.version,
            "uptime": round(uptime, 0),
            "identity": self.identity.to_dict(),
                        "stealth_mode": self.stealth_mode,
            "share_ai": self.share_ai,

            "queries": {"total": self.queries, "success": self.successful,
                        "rate": round(self.successful / max(self.queries, 1) * 100, 1)},
            "memory": self.memory.stats(),
            "peers": {"total": len(self.peers),
                      "available": sum(1 for p in self.peers if p.available)},
            "ws_clients": len(self.ws_clients),
            "local_models": self.local_models,
            "providers": providers_info,
            "web_of_trust": len(self.web_of_trust.trust_edges),
            "rate_limiter": self.rate_limiter.to_dict(),
            "sharing_quota": self.sharing_quota.to_dict(),
            "bandwidth_quota": self.bandwidth_quota.to_dict() if self.bandwidth_quota else {"available": False},
            "credit_system": self.credit_system.to_dict() if self.credit_system else {"available": False},
            "capabilities": self.own_capabilities.to_dict(),
            "gamified_score": GamifiedScore.get_tier(
                self.sharing_quota.calculate_score(self.node_name)
            ),
            "zero_config_peers": len(self.zero_config.get_discovered_peers()),
            "daemon": self.systray.status(),
            # Core modules
            "resource_guard": {
                "available": HAS_RESOURCE_GUARD,
                "state": self.resource_guard._state.value if self.resource_guard else "unavailable",
            } if self.resource_guard else {"available": False, "state": "unavailable"},
            "adaptive_scheduler": {
                "available": HAS_ADAPTIVE_SCHEDULER,
                "strategy": self.adaptive_scheduler.strategy.value if self.adaptive_scheduler else "unavailable",
            } if self.adaptive_scheduler else {"available": False, "strategy": "unavailable"},
            "conversation_store": {"available": HAS_CONVERSATION_STORE} if self.conversation_store else {"available": False},
            "model_share_manager": {"available": HAS_MODEL_SHARE_MANAGER} if self.model_share_manager else {"available": False},
            "model_registry": {"available": HAS_MODEL_REGISTRY, "models": len(self.model_registry._cards)} if self.model_registry and HAS_MODEL_REGISTRY else {"available": False},
            "tracker_client": {
                "available": HAS_TRACKER_CLIENT and self.tracker_client is not None,
                "state": self.tracker_client.state if self.tracker_client else "unavailable",
            } if self.tracker_client else {"available": False, "state": "unavailable"},
        }

    # ========================================================================
    # AUTH
    # ========================================================================

    def _auth_headers(self, path: str = "/api/query") -> Dict[str, str]:
        """Generate auth headers for outgoing requests using BOTH Ed25519/HMAC Bearer token
        AND shared-secret HMAC. Sends both so the receiver can use either method.
        
        CRIT-02 fix: Bearer token now signs {node_name}:{path}:{ts} to prevent replay
        across different endpoints.
        """
        ts = str(int(time.time()))
        # CRIT-02 fix: include path in the signed challenge to prevent cross-endpoint replay
        challenge = f"{self.node_name}:{path}:{ts}"
        token = self.identity.sign(challenge)
        # Also compute shared-secret HMAC for v3 compat fallback
        import hmac as hmac_mod
        hmac_sig = hmac_mod.new(
            self.p2p_secret.encode(), f"{path}:{ts}".encode(), hashlib.sha256).hexdigest()
        return {
            'Authorization': f'Bearer {token}',
            'X-PinkyBrain-Node': self.node_name,
            'X-PinkyBrain-Key': self.identity.public_key_hex,
            'X-PinkyBrain-TS': ts,
            'X-PinkyBrain-Auth': hmac_sig,
            'X-PinkyBrain-Version': '4.2.1'
        }

    def _verify_auth(self, request: web.Request) -> Optional[Dict]:
        """Verify incoming request auth. Returns identity info or None."""
        # Rate limiting first
        client_key = request.remote or "unknown"
        if not self.rate_limiter.allow(client_key):
            logger.debug(f"Auth blocked by rate limiter for {client_key}")
            return None

        # Check Bearer token (Ed25519/HMAC signature)
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            ts = request.headers.get('X-PinkyBrain-TS', '')
            node_name = request.headers.get('X-PinkyBrain-Node', '')
            node_key = request.headers.get('X-PinkyBrain-Key', '')

            # MED-05: Anti-replay timestamp window (30s)
            if ts:
                try:
                    if abs(time.time() - int(ts)) > HMAC_WINDOW_SECONDS:
                        logger.debug(f"Auth rejected: timestamp too old ({abs(time.time() - int(ts)):.0f}s)")
                        return None
                except ValueError:
                    logger.debug(f"Auth rejected: invalid timestamp '{ts}'")
                    return None

            # CRIT-02 fix: include request path in the challenge to prevent cross-endpoint replay
            if node_key and node_name:
                sig = auth[7:]
                challenge = f"{node_name}:{request.path}:{ts}"
                verified = self.identity.verify(challenge, sig, node_key)
                # NEW-01: Nonce check via thread-safe helper
                nonce = f"{node_name}:{request.path}:{ts}"
                if not self._check_and_add_nonce(nonce):
                    logger.debug("Auth rejected: replayed nonce")
                    return None
                if verified:
                    # MED-07: Check token blacklist
                    token_id = hashlib.sha256(f"{node_name}:{sig}:{ts}".encode()).hexdigest()[:32]
                    if self._is_token_blacklisted(token_id):
                        logger.debug(f"Auth rejected: token blacklisted for {node_name}")
                        return None
                    return {"node": node_name, "public_key": node_key, "method": "ed25519"}
                else:
                    # MED-03: no sig/key fragments in logs
                    logger.info(f"Auth rejected: verify failed for node={node_name}")

        # Fallback: shared secret HMAC (v3 compat)
        hmac_auth = request.headers.get('X-PinkyBrain-Auth', '')
        hmac_ts = request.headers.get('X-PinkyBrain-TS', '')
        if hmac_auth and hmac_ts:
            try:
                ts = float(hmac_ts)
                # MED-05: HMAC window reduced to HMAC_WINDOW_SECONDS (30s)
                if abs(time.time() - ts) > HMAC_WINDOW_SECONDS:
                    return None
                # NEW-01: Nonce check for HMAC too
                nonce = f"hmac:{request.path}:{hmac_ts}"
                if not self._check_and_add_nonce(nonce):
                    return None
                path = request.path
                msg = f"{path}:{hmac_ts}"
                import hmac as hmac_mod
                expected_sig = hmac_mod.new(
                    self.p2p_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
                if hmac_mod.compare_digest(hmac_auth, expected_sig):
                    return {"node": "legacy", "method": "hmac"}
            except (ValueError, TypeError):
                pass
        return None

    # ========================================================================
    # STEALTH MODE
    # ========================================================================

    def _stealth_check(self, request: web.Request) -> bool:
        """In stealth mode, reject requests from unknown nodes.
        Returns True if request should be allowed."""
        if not self.stealth_mode:
            return True
        node_key = request.headers.get('X-PinkyBrain-Key', '')
        if node_key and self.web_of_trust.is_trusted(node_key, min_score=0.5):
            return True
        # Check if it's a known peer
        for peer in self.peers:
            if peer.public_key_hex == node_key:
                return True
        return False

    # ========================================================================
    # HTTP API (retrocompatible REST)
    # ========================================================================

    # ========================================================================
    # HIGH-04: Global rate limiter middleware
    # ========================================================================

    @web.middleware
    async def global_rate_limit_middleware(self, request: web.Request, handler):
        """Global rate limiter applied to ALL endpoints.
        Uses X-Forwarded-For (if from trusted proxy) or remote IP.
        Maps None/unknown to unique per-connection IDs.
        """
        # Determine client identifier
        forwarded = request.headers.get('X-Forwarded-For', '')
        # Only trust X-Forwarded-For if request comes from a known proxy
        # (we check if remote is localhost or a configured peer)
        trusted_proxies = {'127.0.0.1', '::1', 'localhost'}
        remote = request.remote or ''
        if forwarded and remote in trusted_proxies:
            # Use the first IP in X-Forwarded-For chain
            client_ip = forwarded.split(',')[0].strip()
        else:
            client_ip = remote

        # Map None/empty to unique ID per connection
        if not client_ip or client_ip == 'unknown':
            client_ip = f'conn-{id(request)}'

        # Apply global rate limiting
        if not self._global_rate_limiter.allow(client_ip):
            return web.json_response(
                {'error': 'Rate limit exceeded'}, status=429,
                headers={'Retry-After': '1'})

        return await handler(request)

    # HIGH-06: CORS middleware
    @web.middleware
    async def cors_middleware(self, request: web.Request, handler):
        """CORS middleware: only allow configured origins."""
        # Build allowed origins from config
        origins = list(CORS_ALLOWED_ORIGINS)
        # Add configured peer addresses
        for peer in self.peers:
            origins.append(f'http://{peer.host}:{peer.port}')
        origins.append(f'http://127.0.0.1:{self.port}')
        origins.append(f'http://localhost:{self.port}')

        origin = request.headers.get('Origin', '')
        is_preflight = request.method == 'OPTIONS'

        if is_preflight:
            resp = web.Response(status=204)
            if origin in origins:
                resp.headers['Access-Control-Allow-Origin'] = origin
                resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
                resp.headers['Access-Control-Allow-Headers'] = 'Authorization, X-PinkyBrain-Node, X-PinkyBrain-Key, X-PinkyBrain-TS, X-PinkyBrain-Auth, X-PinkyBrain-Version, Content-Type'
                resp.headers['Access-Control-Max-Age'] = '86400'
            return resp

        resp = await handler(request)
        if origin in origins:
            resp.headers['Access-Control-Allow-Origin'] = origin
        # Security headers for all responses
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['X-Frame-Options'] = 'DENY'
        resp.headers['X-XSS-Protection'] = '1; mode=block'
        return resp

    async def create_app(self) -> web.Application:
        app = web.Application(
            middlewares=[self.global_rate_limit_middleware, self.cors_middleware]
        )
        # Public endpoints (no auth required, but rate-limited)
        app.router.add_get('/', self.handle_dashboard)
        app.router.add_get('/api/ping', self.handle_ping)
        # Auth-aware endpoints (return minimal info without auth, full info with auth)
        app.router.add_get('/api/status', self.handle_status)
        app.router.add_get('/api/peers', self.handle_peers)
        app.router.add_get('/api/monitor', self.handle_monitor)
        app.router.add_get('/api/agent', self.handle_agent_sidekick)
        # Auth-required endpoints
        app.router.add_post('/api/query', self._auth_required(self.handle_query))
        app.router.add_post('/api/memory/set', self._auth_required(self.handle_memory_set))
        app.router.add_get('/api/memory/{key}', self.handle_memory_get)
        app.router.add_post('/api/memory/sync', self._auth_required(self.handle_memory_sync_push))
        app.router.add_post('/api/memory/push', self._auth_required(self.handle_memory_push))
        app.router.add_post('/api/memory/pull', self._auth_required(self.handle_memory_pull))
        app.router.add_get('/api/brain/status', self.handle_brain_status)
        app.router.add_get('/api/brain/models', self.handle_brain_models)
        app.router.add_post('/api/brain/query', self._auth_required(self.handle_brain_query))
        app.router.add_post('/api/brain/consensus', self.handle_brain_consensus)
        app.router.add_get('/api/quota', self.handle_quota)
        app.router.add_get('/api/quota/{peer}', self.handle_quota)
        app.router.add_post('/api/brain/chain', self._auth_required(self.handle_brain_chain))
        app.router.add_post('/api/trust/sign', self._auth_required(self.handle_trust_sign))
        app.router.add_get('/api/trust/score/{key}', self.handle_trust_score)
        # New endpoints
        app.router.add_get('/api/capabilities', self.handle_capabilities)
        app.router.add_get('/api/score/{peer}', self.handle_gamified_score)
        app.router.add_get('/api/discover', self.handle_discover)
        app.router.add_get('/api/update', self.handle_update_check)
        app.router.add_get('/api/daemon', self.handle_daemon_status)
        app.router.add_post('/api/agent/query', self._auth_required(self.handle_agent_query))
        # WebSocket endpoint
        app.router.add_get('/ws', self.handle_websocket)

        # v5: PinkyBrain Desktop — Static file serving (localhost only)
        web_dir = os.path.join(os.path.dirname(__file__), 'web')
        if os.path.isdir(web_dir):
            app.router.add_static('/ui', web_dir, name='ui_static',
                                  follow_symlinks=False, show_index=False)
            # Serve specific static files at root for direct access
            app.router.add_get('/style.css', self._serve_web_file('style.css'))
            app.router.add_get('/app.js', self._serve_web_file('app.js'))
            app.router.add_get('/api.js', self._serve_web_file('api.js'))

        # ========================================================================
        # v5: PINKYBRAIN DESKTOP UI API ENDPOINTS
        # ========================================================================

        # Chat & Conversations
        app.router.add_post('/api/chat', self._auth_required(self.handle_chat))
        app.router.add_get('/api/conversations', self._auth_required(self.handle_conversations_list))
        app.router.add_get('/api/conversations/{conv_id}', self._auth_required(self.handle_conversation_get))
        app.router.add_delete('/api/conversations/{conv_id}', self._auth_required(self.handle_conversation_delete))
        app.router.add_post('/api/conversations/{conv_id}/export', self._auth_required(self.handle_conversation_export))

        # Resources
        app.router.add_get('/api/resources/status', self._auth_required(self.handle_resources_status))
        app.router.add_post('/api/resources/config', self._auth_required(self.handle_resources_config))

        # Bandwidth Quota
        app.router.add_get('/api/bandwidth', self.handle_bandwidth_status)
        app.router.add_post('/api/bandwidth', self._auth_required(self.handle_bandwidth_config))

        # Credits
        app.router.add_get('/api/credits', self.handle_credits_status)
        app.router.add_get('/api/credits/{peer}', self.handle_credits_account)
        app.router.add_post('/api/credits/reward', self._auth_required(self.handle_credits_reward))

        # Models
        app.router.add_get('/api/models', self._auth_required(self.handle_models_list))
        app.router.add_post('/api/models/{name}/share', self._auth_required(self.handle_model_share))
        app.router.add_post('/api/models/{name}/unshare', self._auth_required(self.handle_model_unshare))

        # v5.2: Model Registry — catalogue, recherche, recommandations
        app.router.add_get('/api/registry', self.handle_registry_list)
        app.router.add_get('/api/registry/stats', self.handle_registry_stats)
        app.router.add_get('/api/registry/{name}', self.handle_registry_info)
        app.router.add_post('/api/registry', self._auth_required(self.handle_registry_add))
        app.router.add_delete('/api/registry/{name}', self._auth_required(self.handle_registry_remove))
        app.router.add_put('/api/registry/{name}', self._auth_required(self.handle_registry_update))
        app.router.add_get('/api/registry/search/{query}', self.handle_registry_search)
        app.router.add_get('/api/registry/recommend', self.handle_registry_recommend)
        app.router.add_get('/api/registry/mesh', self.handle_registry_mesh)
        app.router.add_get('/api/registry/wishlist', self.handle_registry_wishlist)
        app.router.add_post('/api/registry/wishlist/{name}', self._auth_required(self.handle_registry_wishlist_add))
        app.router.add_post('/api/registry/{name}/share', self._auth_required(self.handle_registry_share))
        app.router.add_post('/api/registry/{name}/unshare', self._auth_required(self.handle_registry_unshare))
        app.router.add_post('/api/registry/purge', self._auth_required(self.handle_registry_purge))
        app.router.add_get('/api/registry/stale', self.handle_registry_stale)

        # v5.2: Network Sync — DNS dynamique + sync mesh
        app.router.add_get('/api/network/sync', self.handle_network_sync_status)
        app.router.add_post('/api/network/sync', self._auth_required(self.handle_network_sync_run))
        app.router.add_get('/api/network/dns', self.handle_dns_list)
        app.router.add_get('/api/network/dns/stats', self.handle_dns_stats)
        app.router.add_get('/api/network/missing', self.handle_missing_models)

        # Network
        app.router.add_get('/api/network/private/peers', self._auth_required(self.handle_network_private_peers))
        app.router.add_get('/api/network/mesh/nodes', self._auth_required(self.handle_network_mesh_nodes))
        app.router.add_post('/api/network/mesh/join', self._auth_required(self.handle_network_mesh_join))
        app.router.add_post('/api/network/mesh/leave', self._auth_required(self.handle_network_mesh_leave))

        # Model Networks (v5.2)
        app.router.add_get('/api/model-networks', self._auth_required(self.handle_model_networks_get))
        app.router.add_post('/api/model-networks', self._auth_required(self.handle_model_networks_save))
        app.router.add_post('/api/model-networks/{network_id}/generate-secret', self._auth_required(self.handle_model_networks_generate_secret))

        # Config
        app.router.add_get('/api/config', self._auth_required(self.handle_config_get))
        app.router.add_post('/api/config', self._auth_required(self.handle_config_set))

        # Specialist & Multi-Model endpoints
        app.router.add_get('/api/specialties', self.handle_specialties_list)
        app.router.add_get('/api/specialties/{name}/models', self.handle_specialty_models)
        app.router.add_post('/api/multi', self._auth_required(self.handle_multi_model_query))

        return app

    def _auth_required(self, handler):
        """Decorator: require auth for a handler."""
        async def wrapper(request: web.Request):
            # Stealth mode check
            if self.stealth_mode and not self._stealth_check(request):
                return web.Response(status=404, text="Not found")
            auth_result = self._verify_auth(request)
            if auth_result is None:
                return web.Response(status=401, text="Unauthorized")
            request['auth'] = auth_result
            return await handler(request)
        return wrapper

    def _serve_web_file(self, filename):
        """Return a handler that serves a static web file with correct content type."""
        web_dir = os.path.join(os.path.dirname(__file__), 'web')
        content_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
        }
        filepath = os.path.join(web_dir, filename)
        ext = os.path.splitext(filename)[1]
        ct = content_types.get(ext, 'application/octet-stream')

        async def handler(request: web.Request) -> web.Response:
            # Only serve on localhost
            peername = request.transport.get_extra_info('peername')
            if peername and peername[0] not in ('127.0.0.1', '::1', '::ffff:127.0.0.1', 'localhost'):
                return web.Response(status=403, text="Forbidden: localhost only")
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                return web.Response(text=content, content_type=ct)
            except FileNotFoundError:
                return web.Response(status=404, text="Not found")
        return handler

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        """Serve the PinkyBrain Desktop web UI. Falls back to legacy dashboard if files not found."""
        web_dir = os.path.join(os.path.dirname(__file__), 'web')
        index_path = os.path.join(web_dir, 'index.html')
        if os.path.isfile(index_path):
            # Serve the new Desktop UI
            # Only allow localhost access
            peername = request.transport.get_extra_info('peername')
            if peername and peername[0] not in ('127.0.0.1', '::1', '::ffff:127.0.0.1', 'localhost'):
                return web.Response(status=403, text="Forbidden: localhost only")
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # LOW-04: CSP header
                return web.Response(text=content, content_type='text/html',
                                     headers={'Content-Security-Policy': CSP_HEADER})
            except OSError:
                pass

        # Legacy dashboard fallback
        status = self.get_status()
        uptime = status['uptime']
        hours, remainder = divmod(int(uptime), 3600)
        mins, secs = divmod(remainder, 60)

        html = f"""<!DOCTYPE html>
<html><head><title>PinkyBrain v{self.version}</title>
<style>
body {{ font-family: system-ui; background: #0a0a0a; color: #e0e0e0; margin: 2rem; }}
.card {{ background: #1a1a2e; border: 1px solid #333; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }}
.header {{ text-align: center; padding: 2rem; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
.stat {{ display: flex; justify-content: space-between; padding: 0.3rem 0; }}
.label {{ color: #888; }} .value {{ color: #4ecdc4; font-weight: bold; }}
.peer {{ padding: 0.5rem; border-left: 3px solid #4ecdc4; margin: 0.3rem 0; }}
.ok {{ color: #4ecdc4; }} .ko {{ color: #e74c3c; }}
h1 {{ color: #4ecdc4; }} h2 {{ color: #888; font-size: 0.9rem; text-transform: uppercase; }}
.stealth {{ background: #2d1b00; border-color: #e67e22; padding: 0.5rem; border-radius: 4px; color: #e67e22; margin: 1rem 0; }}
</style></head><body>
<div class="header">
<h1>🌐 PinkyBrain v{self.version}</h1>
<div class="subtitle">Node: <strong>{self.node_name}</strong> | Uptime: {hours}h {mins}m {secs}s</div>
{'<div class="stealth">🔒 STEALTH MODE ACTIVE</div>' if self.stealth_mode else ''}
{'<div class="stealth" style="border-color:#4ecdc4;color:#4ecdc4;">📤 AI SHARING ENABLED</div>' if self.share_ai else ''}
</div>
<div class="grid">
<div class="card"><h2>Queries</h2>
<div class="stat"><span class="label">Total</span><span class="value">{status['queries']['total']}</span></div>
<div class="stat"><span class="label">Success</span><span class="value">{status['queries']['rate']}%</span></div>
<div class="stat"><span class="label">Memory</span><span class="value">{status['memory']['active_entries']} keys</span></div>
<div class="stat"><span class="label">Models</span><span class="value">{', '.join(self.local_models)}</span></div>
</div>
<div class="card"><h2>Network</h2>
<div class="stat"><span class="label">Peers</span><span class="value">{status['peers']['available']}/{status['peers']['total']}</span></div>
<div class="stat"><span class="label">WS Clients</span><span class="value">{status['ws_clients']}</span></div>
<div class="stat"><span class="label">Trust Links</span><span class="value">{status['web_of_trust']}</span></div>
<div class="stat"><span class="label">Identity</span><span class="value">{self.identity.fingerprint}</span></div>
</div>
</div>
<div class="card"><h2>Peers</h2>"""

        for p in self.peers:
            icon = "✅" if p.available else "❌"
            cb_state = p.circuit_breaker.state
            html += f"""<div class="peer">
<span class="{'ok' if p.available else 'ko'}">{icon} {html.escape(p.name)}</span>
{html.escape(p.host)}:{p.port} — {round(p.latency, 1)}ms — CB:{cb_state}
</div>"""

        if not self.peers:
            html += "<div>No peers connected</div>"

        html += "</div>"

        # Providers section
        html += '<div class="card"><h2>Providers</h2>'
        if self.providers:
            for name, provider in self.providers.items():
                status_icon = "\u2705" if provider.enabled else "\u274c"
                model_list = ', '.join(provider.models[:5])
                if len(provider.models) > 5:
                    model_list += f'... (+{len(provider.models) - 5} more)'
                extra = ""
                if isinstance(provider, OllamaProvider):
                    extra = f' @ {provider.host}:{provider.port}'
                elif isinstance(provider, (OpenAIProvider, OpenAICompatibleProvider, AnthropicProvider)):
                    extra = f' @ {provider.base_url}'
                html += f'<div class="peer">{status_icon} <strong>{name}</strong> ({provider.provider_type}){extra}<br/><span class="label">Models:</span> {model_list}</div>'
        else:
            html += '<div>Aucun fournisseur configuré</div>'
        html += '</div>'

        # Gamified Score section
        html += '<div class="card"><h2>🤝 Score de Partage</h2>'
        own_score = self.sharing_quota.calculate_score(self.node_name)
        own_tier = GamifiedScore.get_tier(own_score)
        html += f"""<div style="margin:1rem 0">
        <div style="font-size:1.5rem;margin-bottom:0.5rem">{own_tier['tier']}</div>
        <div style="background:#1a1a2e;border:1px solid #333;border-radius:4px;overflow:hidden">
          <div style="background:{own_tier['color']};width:{own_score}%;height:8px"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:4px">
          <span class="label">Score: {own_score:.1f}/100</span>"""
        if own_tier['next_tier']:
            html += f'<span class="label">Suivant: {own_tier["next_tier"]["name"]} ({own_tier["next_tier"]["score_needed"]})</span>'
        else:
            html += '<span class="label">🏆 NIVEAU MAX</span>'
        html += '</div></div>'
        if self.peers:
            html += '<h2>Scores des Pairs</h2>'
            for p in self.peers:
                peer_score = self.sharing_quota.calculate_score(p.name)
                peer_tier = GamifiedScore.get_tier(peer_score)
                html += f'<div class="stat"><span>{html.escape(p.name)}</span><span style="color:{peer_tier["color"]}">{peer_tier["tier"]} ({peer_score:.1f})</span></div>'
        html += '</div>'

        # Capabilities section
        html += '<div class="card"><h2>🖥️ Capacités</h2>'
        caps = self.own_capabilities
        gpu_str = f"✅ {caps.gpu_name} ({caps.gpu_vram_mb}Mo)" if caps.gpu_available else "❌ Aucun"
        html += f'<div class="stat"><span class="label">GPU</span><span class="value">{gpu_str}</span></div>'
        html += f'<div class="stat"><span class="label">CPU</span><span class="value">{caps.cpu_cores} cœurs</span></div>'
        html += f'<div class="stat"><span class="label">RAM</span><span class="value">{caps.ram_total_mb}Mo</span></div>'
        html += f'<div class="stat"><span class="label">Modèle Max</span><span class="value">{caps.max_model_category.upper()}</span></div>'
        if self.model_negotiator.peer_caps:
            html += '<h2>Matériel des Pairs</h2>'
            for name, pcaps in self.model_negotiator.peer_caps.items():
                pgpu = f"✅ {pcaps.gpu_name}" if pcaps.gpu_available else "❌"
                html += f'<div class="stat"><span>{name}</span><span>{pgpu} | {pcaps.max_model_category.upper()}</span></div>'
        html += '</div>'

        # Zero-Config discovered peers
        zc_peers = self.zero_config.get_discovered_peers()
        if zc_peers:
            html += '<div class="card"><h2>📡 Découverte Zero-Config</h2>'
            for p in zc_peers:
                html += f'<div class="peer">🔍 {p["name"]} @ {p["host"]}:{p["port"]}</div>'
            html += '</div>'

        html += """"</body></html>"""
        return web.Response(text=html, content_type='text/html')

    async def handle_status(self, request: web.Request) -> web.Response:
        # HIGH-03 fix: Return minimal info for unauthenticated requests
        auth = self._verify_auth(request)
        if auth is None:
            # Minimal public info
            return web.json_response({
                'node': self.node_name,
                'version': self.version,
                'status': 'online'
            })
        return web.json_response(self.get_status())

    async def handle_ping(self, request: web.Request) -> web.Response:
        return web.json_response({"pong": True, "node": self.node_name,
                                   "version": self.version, "time": time.time()})

    async def handle_query(self, request: web.Request) -> web.Response:
        data = await request.json()
        prompt = data.get("prompt", "")
        model = data.get("model")
        strategy = data.get("strategy", "auto")
        specialty = data.get("specialty")  # v5: specialty-based routing
        models = data.get("models")  # v5: force specific models
        specialties = data.get("specialties")  # v5: force multiple specialties
        
        # HIGH-01 fix: Input validation
        if not prompt or len(prompt) > MAX_PROMPT_LENGTH:
            return web.json_response(
                {"error": f"prompt must be 1-{MAX_PROMPT_LENGTH} characters"}, status=400)
        if model and not ALLOWED_MODEL_PATTERN.match(model):
            return web.json_response(
                {"error": "invalid model name (allowed: alphanumeric, dots, dashes, colons, slashes)"},
                status=400)
        if strategy not in ALLOWED_STRATEGIES:
            return web.json_response(
                {"error": f"invalid strategy, allowed: {', '.join(sorted(ALLOWED_STRATEGIES))}"},
                status=400)
        
        # Check bandwidth quota for mesh requests
        if self.bandwidth_quota:
            is_peer = request.get('auth', {}).get('node', '') != self.node_name
            if is_peer and not self.bandwidth_quota.can_transfer():
                remaining = self.bandwidth_quota.get_remaining_data_mb()
                return web.json_response({
                    "error": "bandwidth quota exceeded",
                    "remaining_mb": round(remaining, 1),
                    "reset_at": self.bandwidth_quota._current_period.period_end,
                    "hint": "Monthly data quota exceeded. Increase bandwidth_quota.monthly_data_gb or wait for reset."
                }, status=429)

        # Check if this is a peer request
        auth_info = request.get('auth', {})
        is_peer_request = auth_info.get('node', self.node_name) != self.node_name
        
        # If share_ai is False and this comes from a peer, reject
        if is_peer_request and not self.share_ai:
            return web.json_response({
                "error": "AI sharing disabled on this node",
                "share_ai": False
            }, status=403)
        
        # v5.2: Credit check for peer requests (replaces old quota system)
        if is_peer_request:
            peer_name = auth_info.get('node', 'unknown')
            self.sharing_quota.record_query_made(peer_name)

            # Determine query cost
            query_type = "simple"
            model_count = 1
            if models and len(models) > 1:
                query_type = "multi"
                model_count = len(models)
            elif specialty:
                query_type = "specialty"

            # Rate limit check (still enforced)
            if not self.sharing_quota.allow_query(peer_name):
                score = self.sharing_quota.calculate_score(peer_name)
                quota = self.sharing_quota.get_quota(peer_name)
                return web.json_response({
                    "error": "Rate limit exceeded",
                    "peer": peer_name,
                    "score": score,
                    "quota_queries_per_minute": quota,
                    "hint": "Share more models or increase uptime to raise your rate limit"
                }, status=429)

            # v5.2: Credit system check
            if self.credit_system:
                can_afford = self.credit_system.can_afford(peer_name, QUERY_COSTS.get(query_type, 1))
                if not can_afford:
                    acc = self.credit_system.get_or_create(peer_name)
                    return web.json_response({
                        "error": "Insufficient credits",
                        "peer": peer_name,
                        "balance": round(acc.balance, 1),
                        "cost": QUERY_COSTS.get(query_type, 1),
                        "tier": self.credit_system.get_tier(peer_name).value,
                        "hint": "Share more resources (models, GPU, memory) to earn credits, or wait for monthly reset"
                    }, status=402)
                # Spend credits
                success, cost = self.credit_system.spend(peer_name, query_type, model_count)
                if not success:
                    acc = self.credit_system.get_or_create(peer_name)
                    return web.json_response({
                        "error": "Insufficient credits",
                        "peer": peer_name,
                        "balance": round(acc.balance, 1),
                        "cost": cost,
                        "hint": "Share more resources to earn credits"
                    }, status=402)
        
        # Specialty-based routing — if specialty/models specified, use SpecialistRouter
        if self.specialist_router and (specialty or models or specialties):
            routing = self.specialist_router.route(
                prompt,
                available=self.local_models,
                specialty=specialty,
                models=models,
                specialties=specialties,
            )
            selected_models = routing["models"]
            if len(selected_models) == 1:
                # Single model — use normal query with the selected model
                result = await self.query(prompt, selected_models[0], strategy)
                result["specialist_routing"] = routing
            else:
                # Multiple models — use multi-model executor
                async def _query_one(m, p):
                    return await self.query(p, m, strategy)
                multi_result = await self.multi_model_executor.execute(
                    prompt, selected_models, MultiModelMode.SPECIALIST, query_fn=_query_one
                )
                result = multi_result.to_dict()
                result["specialist_routing"] = routing
            return web.json_response(result)
        
        result = await self.query(prompt, model, strategy)
        return web.json_response(result)

    async def handle_memory_set(self, request: web.Request) -> web.Response:
        data = await request.json()
        key = data.get("key", "")
        value = data.get("value")
        ttl = data.get("ttl")
        author = request.get('auth', {}).get('node', self.node_name)
        if not key:
            return web.json_response({"error": "key required"}, status=400)
        self.memory.set(key, value, ttl, author=author)
        # Gossip the update
        await self._gossip_broadcast({
            "type": "memory_update", "key": key,
            "entry": self.memory.store.get(key, {}),
            "source": self.node_name
        })
        return web.json_response({"status": "ok", "key": key})

    async def handle_memory_get(self, request: web.Request) -> web.Response:
        # HIGH-03: require auth for memory access
        auth = self._verify_auth(request)
        if auth is None:
            return web.Response(status=401, text='Unauthorized')
        key = request.match_info['key']
        value = self.memory.get(key)
        if value is None:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({"key": key, "value": value})

    async def handle_memory_sync_push(self, request: web.Request) -> web.Response:
        """Full memory sync push from another node."""
        data = await request.json()
        entries = data.get("entries", data.get("memory", {}))
        merged = self.memory.merge_from_sync(entries)
        self.log_event("sync", f"Merged {merged} entries via HTTP push")
        return web.json_response({"keys_merged": merged, "status": "ok"})

    async def handle_memory_push(self, request: web.Request) -> web.Response:
        """Push specific entries to this node (CRDT merge)."""
        data = await request.json()
        entries = data.get("entries", {})
        merged = self.memory.merge_from_sync(entries)
        return web.json_response({"keys_merged": merged, "status": "ok"})

    async def handle_memory_pull(self, request: web.Request) -> web.Response:
        """Pull entries newer than given vector clock (incremental sync)."""
        data = await request.json()
        since_vc = data.get("vector_clock", {})
        delta = self.memory.get_delta_since(since_vc)
        return web.json_response({"entries": delta, "vector_clock": self.memory.vector_clock.to_dict()})

    async def handle_peers(self, request: web.Request) -> web.Response:
        # HIGH-03 fix: Hide peer details for unauthenticated requests
        auth = self._verify_auth(request)
        if auth is None:
            # Minimal info only
            return web.json_response([
                {'name': p.name, 'available': p.available} for p in self.peers
            ])
        return web.json_response([p.to_dict() for p in self.peers])

    async def handle_quota(self, request: web.Request) -> web.Response:
        """Get sharing quota info for all peers or a specific peer."""
        peer_name = request.match_info.get('peer')
        if peer_name:
            info = self.sharing_quota.get_peer_info(peer_name)
            return web.json_response(info)
        return web.json_response(self.sharing_quota.to_dict())

    async def handle_monitor(self, request: web.Request) -> web.Response:
        # HIGH-03 fix: Require auth for monitoring data
        auth = self._verify_auth(request)
        if auth is None:
            return web.Response(status=401, text='Unauthorized')
        if not HAS_PSUTIL:
            return web.json_response({"error": "psutil not available"}, status=503)
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return web.json_response({
            "cpu": cpu, "mem_percent": mem.percent,
            "mem_total_gb": round(mem.total / (1024**3), 1),
            "peers": len(self.peers),
            "uptime": time.time() - self.start_time,
            "load_balancer": self.load_balancer.node_scores
        })

    async def handle_brain_status(self, request: web.Request) -> web.Response:
        if self.brain_llm:
            return web.json_response(self.brain_llm.status())
        return web.json_response({"error": "brain_llm not available"}, status=503)

    async def handle_brain_models(self, request: web.Request) -> web.Response:
        if self.brain_llm:
            return web.json_response(self.brain_llm.status().get("models", {}))
        return web.json_response({}, status=503)

    async def handle_brain_query(self, request: web.Request) -> web.Response:
        if not self.brain_llm:
            return web.json_response({"error": "brain_llm not available"}, status=503)
        data = await request.json()
        result = await self.brain_llm.query(
            data.get("prompt", ""), model=data.get("model"),
            strategy=data.get("strategy", "auto"))
        return web.json_response({
            "response": result.response, "model": result.model,
            "provider": result.provider, "latency_ms": result.latency_ms,
            "tokens_used": result.tokens_used, "confidence": result.confidence
        })

    async def handle_brain_consensus(self, request: web.Request) -> web.Response:
        data = await request.json()
        result = await self.ensemble.query_ensemble(
            self.session, self.peers, data.get("prompt", ""), data.get("model"))
        return web.json_response(result)

    async def handle_brain_chain(self, request: web.Request) -> web.Response:
        if not self.brain_llm:
            return web.json_response({"error": "brain_llm not available"}, status=503)
        data = await request.json()
        result = await self.brain_llm.query(
            data.get("prompt", ""), strategy="chain")
        return web.json_response({
            "response": result.response, "model": result.model,
            "provider": result.provider, "latency_ms": result.latency_ms
        })

    async def handle_trust_sign(self, request: web.Request) -> web.Response:
        """Sign (vouch for) another node's public key."""
        data = await request.json()
        target_key = data.get("public_key", "")
        if not target_key:
            return web.json_response({"error": "public_key required"}, status=400)
        self.web_of_trust.add_trust(self.identity.public_key_hex, target_key)
        # Gossip the trust edge
        await self._gossip_broadcast({
            "type": "trust_sign",
            "signer": self.identity.public_key_hex,
            "target": target_key,
            "source": self.node_name
        })
        score = self.web_of_trust.trust_score(target_key)
        return web.json_response({"status": "signed", "trust_score": score})

    async def handle_trust_score(self, request: web.Request) -> web.Response:
        key = request.match_info['key']
        score = self.web_of_trust.trust_score(key)
        return web.json_response({"public_key": key, "trust_score": score,
                                   "is_trusted": self.web_of_trust.is_trusted(key)})

    # ========================================================================
    # Capabilities, Score, Discovery, Update, Daemon endpoints
    # ========================================================================
    # v5: PINKYBRAIN DESKTOP UI API HANDLERS
    # ========================================================================

    # --- Conversation storage ---

    def _conv_dir(self) -> Path:
        """Return the conversations directory, creating it if needed."""
        conv_dir = Path.home() / ".pinkybrain" / "conversations"
        conv_dir.mkdir(parents=True, exist_ok=True)
        return conv_dir

    def _conv_path(self, conv_id: str) -> Optional[Path]:
        """Return the path for a single conversation file."""
        # Validate conv_id to prevent path traversal
        if '/' in conv_id or '\\' in conv_id or '..' in conv_id:
            return None
        return self._conv_dir() / f"{conv_id}.json"

    def _load_conversation(self, conv_id: str) -> Optional[Dict]:
        """Load a conversation from disk."""
        path = self._conv_path(conv_id)
        if path is None or not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load conversation {conv_id}: {e}")
            return None

    def _save_conversation(self, conv_id: str, data: Dict) -> bool:
        """Save a conversation to disk."""
        path = self._conv_path(conv_id)
        if path is None:
            return False
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            logger.error(f"Failed to save conversation {conv_id}: {e}")
            return False

    # --- Chat endpoint ---

    async def handle_chat(self, request: web.Request) -> web.Response:
        """POST /api/chat — Send a message, receive an AI response.
        Supports both regular JSON responses and SSE streaming.
        Body: {"message": "...", "model": "...", "strategy": "auto", "conversation_id": "..."}
        """
        data = await request.json()
        message = data.get("message", "")
        model = data.get("model")
        strategy = data.get("strategy", "auto")
        conv_id = data.get("conversation_id")
        stream = data.get("stream", False)

        if not message or len(message) > MAX_PROMPT_LENGTH:
            return web.json_response(
                {"error": f"message must be 1-{MAX_PROMPT_LENGTH} characters"}, status=400)
        if model and not ALLOWED_MODEL_PATTERN.match(model):
            return web.json_response(
                {"error": "invalid model name"}, status=400)
        if strategy not in ALLOWED_STRATEGIES:
            return web.json_response(
                {"error": f"invalid strategy, allowed: {', '.join(sorted(ALLOWED_STRATEGIES))}"}, status=400)

        # Auto-create or load conversation
        if conv_id:
            if '/' in conv_id or '\\' in conv_id or '..' in conv_id:
                return web.json_response({"error": "invalid conversation_id"}, status=400)
            conv = self._load_conversation(conv_id)
            if conv is None:
                return web.json_response({"error": "conversation not found"}, status=404)
        else:
            conv_id = f"conv_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            conv = {
                "id": conv_id,
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
                "messages": [],
                "metadata": {"model": model or "auto", "strategy": strategy, "tags": []}
            }

        # Add user message
        conv["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })

        # Query AI
        result = await self.query(message, model, strategy)

        # Add assistant response
        conv["messages"].append({
            "role": "assistant",
            "content": result.get("response", ""),
            "model": result.get("model", model or "auto"),
            "source": result.get("source", "local"),
            "tokens_used": result.get("tokens_used", 0),
            "latency_ms": result.get("latency_ms", 0),
            "timestamp": datetime.now().isoformat()
        })
        conv["updated"] = datetime.now().isoformat()

        # Save conversation
        self._save_conversation(conv_id, conv)

        if stream:
            # SSE streaming response
            resp = web.StreamResponse(
                status=200,
                reason='OK',
                headers={'Content-Type': 'text/event-stream',
                          'Cache-Control': 'no-cache',
                          'Connection': 'keep-alive'}
            )
            await resp.prepare(request)
            await resp.write(f"data: {json.dumps({'type': 'message_start', 'conversation_id': conv_id})}\n\n".encode())
            response_text = result.get("response", "")
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                await resp.write(f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n".encode())
                await asyncio.sleep(0.01)
            await resp.write(f"data: {json.dumps({'type': 'message_end', 'conversation_id': conv_id, 'latency_ms': result.get('latency_ms', 0)})}\n\n".encode())
            await resp.write_eof()
            return resp

        return web.json_response({
            "conversation_id": conv_id,
            "message": conv["messages"][-1],
            "model": result.get("model", model or "auto"),
            "source": result.get("source", "local"),
            "latency_ms": result.get("latency_ms", 0),
            "tokens_used": result.get("tokens_used", 0)
        })

    # --- Conversation endpoints ---

    async def handle_conversations_list(self, request: web.Request) -> web.Response:
        """GET /api/conversations — List all conversations."""
        conv_dir = self._conv_dir()
        conversations = []
        for f in sorted(conv_dir.glob("conv_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                conversations.append({
                    "id": data.get("id", f.stem),
                    "created": data.get("created", ""),
                    "updated": data.get("updated", ""),
                    "message_count": len(data.get("messages", [])),
                    "model": data.get("metadata", {}).get("model", "unknown"),
                    "tags": data.get("metadata", {}).get("tags", [])
                })
            except (json.JSONDecodeError, OSError):
                continue
        return web.json_response({"conversations": conversations})

    async def handle_conversation_get(self, request: web.Request) -> web.Response:
        """GET /api/conversations/{id} — Load a conversation."""
        conv_id = request.match_info['conv_id']
        conv = self._load_conversation(conv_id)
        if conv is None:
            return web.json_response({"error": "conversation not found"}, status=404)
        return web.json_response(conv)

    async def handle_conversation_delete(self, request: web.Request) -> web.Response:
        """DELETE /api/conversations/{id} — Delete a conversation."""
        conv_id = request.match_info['conv_id']
        path = self._conv_path(conv_id)
        if path is None or not path.exists():
            return web.json_response({"error": "conversation not found"}, status=404)
        try:
            path.unlink()
            return web.json_response({"deleted": conv_id})
        except OSError as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_conversation_export(self, request: web.Request) -> web.Response:
        """POST /api/conversations/{id}/export — Export a conversation.
        Body: {"format": "markdown" | "json" | "txt"}
        """
        conv_id = request.match_info['conv_id']
        conv = self._load_conversation(conv_id)
        if conv is None:
            return web.json_response({"error": "conversation not found"}, status=404)

        data = await request.json()
        fmt = data.get("format", "markdown")
        if fmt not in ("markdown", "json", "txt"):
            return web.json_response({"error": "format must be markdown, json, or txt"}, status=400)

        messages = conv.get("messages", [])

        if fmt == "json":
            return web.json_response(conv)
        elif fmt == "markdown":
            lines = [f"# Conversation: {conv_id}", f"Created: {conv.get('created', '')}", ""]
            for msg in messages:
                role = msg.get("role", "unknown").capitalize()
                content = msg.get("content", "")
                model_info = f" ({msg.get('model', '')})" if msg.get("model") else ""
                lines.append(f"**{role}{model_info}:** {content}")
                lines.append("")
            return web.Response(text="\n".join(lines), content_type="text/markdown")
        else:  # txt
            lines = []
            for msg in messages:
                role = msg.get("role", "unknown").capitalize()
                lines.append(f"{role}: {msg.get('content', '')}")
            return web.Response(text="\n".join(lines), content_type="text/plain")

    # --- Resource endpoints ---

    async def handle_resources_status(self, request: web.Request) -> web.Response:
        """GET /api/resources/status — Current system resource state."""
        if not HAS_PSUTIL:
            return web.json_response({"error": "psutil not available"}, status=503)
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        mesh_config = self.config.get("public_mesh", {})
        max_cpu = mesh_config.get("max_cpu_percent", 30)
        max_ram = mesh_config.get("max_ram_share_mb", 2048)
        gpu_share = mesh_config.get("gpu_share", False)

        gpu_info = None
        if self.own_capabilities.gpu_available:
            gpu_info = {"name": self.own_capabilities.gpu_name, "available": True}

        # Use Resource Guard for sharing state if available
        if self.resource_guard:
            guard = self.resource_guard
            sharing_active = guard.can_accept_request()
            guard_info = guard.get_status()
        else:
            sharing_active = not (cpu_percent > 70 or mem.percent > 85)
            guard_info = None

        response = {
            "cpu": {"percent": cpu_percent, "cores": psutil.cpu_count() if HAS_PSUTIL else os.cpu_count(), "max_share_percent": max_cpu},
            "ram": {
                "total_mb": round(mem.total / 1024 / 1024),
                "available_mb": round(mem.available / 1024 / 1024),
                "used_percent": mem.percent,
                "max_share_mb": max_ram
            },
            "disk": {"total_gb": round(disk.total / 1024 / 1024 / 1024, 1), "used_percent": disk.percent},
            "gpu": gpu_info,
            "sharing": {
                "active": sharing_active,
                "cpu_available": max(0, max_cpu - cpu_percent),
                "ram_available_mb": min(max_ram, round(mem.available * 0.5 / 1024 / 1024)),
                "gpu_share": gpu_share
            },
            "contribution_score": self.sharing_quota.calculate_score(self.node_name)
        }
        if guard_info:
            response["resource_guard"] = guard_info
        return web.json_response(response)

    async def handle_resources_config(self, request: web.Request) -> web.Response:
        """POST /api/resources/config — Modify resource sharing limits.
        Requires explicit confirmation.
        """
        data = await request.json()
        if not data.get("confirm"):
            return web.json_response({
                "error": "Resource changes require explicit confirmation",
                "hint": "Set 'confirm': true in your request"
            }, status=400)

        mesh_config = self.config.setdefault("public_mesh", {})
        if "max_cpu_percent" in data:
            val = data["max_cpu_percent"]
            if not isinstance(val, (int, float)) or val < 0 or val > 100:
                return web.json_response({"error": "max_cpu_percent must be 0-100"}, status=400)
            mesh_config["max_cpu_percent"] = val
        if "max_ram_share_mb" in data:
            val = data["max_ram_share_mb"]
            if not isinstance(val, (int, float)) or val < 0:
                return web.json_response({"error": "max_ram_share_mb must be >= 0"}, status=400)
            mesh_config["max_ram_share_mb"] = val
        if "gpu_share" in data:
            mesh_config["gpu_share"] = bool(data["gpu_share"])
        if "bandwidth_limit_kbps" in data:
            val = data["bandwidth_limit_kbps"]
            if not isinstance(val, (int, float)) or val < 0:
                return web.json_response({"error": "bandwidth_limit_kbps must be >= 0"}, status=400)
            mesh_config["bandwidth_limit_kbps"] = val

        self._persist_config()
        self.log_event("resources", f"Resource config updated: {data}")
        return web.json_response({"status": "updated", "public_mesh": mesh_config})

    # --- Bandwidth Quota endpoints ---

    async def handle_bandwidth_status(self, request: web.Request) -> web.Response:
        """GET /api/bandwidth — Statut du quota de bande passante."""
        if not self.bandwidth_quota:
            return web.json_response({"available": False, "error": "bandwidth_quota module not loaded"})
        return web.json_response(self.bandwidth_quota.get_status())

    async def handle_bandwidth_config(self, request: web.Request) -> web.Response:
        """POST /api/bandwidth — Mettre à jour le quota de bande passante.

        Body: {"monthly_data_gb": 10, "bandwidth_limit_kbps": 10000, "quota_period": "monthly"}
        """
        if not self.bandwidth_quota:
            return web.json_response({"error": "bandwidth_quota module not loaded"}, status=503)

        data = await request.json()

        # Valider et mettre à jour
        monthly_gb = data.get("monthly_data_gb")
        bw_kbps = data.get("bandwidth_limit_kbps")
        period = data.get("quota_period")

        # Validation
        if monthly_gb is not None and (monthly_gb < 0 or monthly_gb > 100):
            return web.json_response({"error": "monthly_data_gb must be between 0 and 100"}, status=400)
        if bw_kbps is not None and (bw_kbps < 0 or bw_kbps > 100000):
            return web.json_response({"error": "bandwidth_limit_kbps must be between 0 and 100000"}, status=400)
        if period is not None and period not in ("monthly", "weekly", "daily"):
            return web.json_response({"error": "quota_period must be monthly, weekly, or daily"}, status=400)

        self.bandwidth_quota.update_config(
            monthly_data_gb=monthly_gb,
            bandwidth_limit_kbps=bw_kbps,
            period=period,
        )

        # Persister dans la config
        bw_config = self.config.get("bandwidth_quota", {})
        if monthly_gb is not None:
            bw_config["monthly_data_gb"] = monthly_gb
        if bw_kbps is not None:
            bw_config["bandwidth_limit_kbps"] = bw_kbps
        if period is not None:
            bw_config["quota_period"] = period
        self.config["bandwidth_quota"] = bw_config
        self._persist_config()

        self.log_event("bandwidth", f"Bandwidth quota updated: {data}")
        return web.json_response({"status": "updated", "bandwidth_quota": self.bandwidth_quota.get_status()})

    # --- Credit System endpoints ---

    async def handle_credits_status(self, request: web.Request) -> web.Response:
        """GET /api/credits — Status complet du système de crédits."""
        if not self.credit_system:
            return web.json_response({"available": False, "error": "credit_system module not loaded"})
        self.credit_system.check_monthly_reset()
        return web.json_response(self.credit_system.to_dict())

    async def handle_credits_account(self, request: web.Request) -> web.Response:
        """GET /api/credits/{peer} — Compte de crédits d'un nœud."""
        if not self.credit_system:
            return web.json_response({"available": False})
        peer_name = request.match_info.get('peer', self.node_name)
        self.credit_system.check_monthly_reset()
        return web.json_response(self.credit_system.get_account_info(peer_name))

    async def handle_credits_reward(self, request: web.Request) -> web.Response:
        """POST /api/credits/reward — Accorder manuellement des crédits (admin).

        Body: {"node": "peer_name", "type": "models|gpu|uptime|memory|reputation", "amount": 50}
        """
        if not self.credit_system:
            return web.json_response({"error": "credit_system module not loaded"}, status=503)
        data = await request.json()
        node = data.get("node", "")
        reward_type = data.get("type", "")
        amount = data.get("amount", 0)

        if not node:
            return web.json_response({"error": "node is required"}, status=400)

        if reward_type == "models":
            self.credit_system.reward_models(node, int(amount / 50) or 1)
        elif reward_type == "gpu":
            self.credit_system.reward_gpu(node)
        elif reward_type == "uptime":
            self.credit_system.reward_uptime(node, amount)
        elif reward_type == "memory":
            self.credit_system.reward_memory_chunks(node, int(amount / 2) or 1)
        elif reward_type == "reputation":
            self.credit_system.reward_reputation(node, amount)
        elif amount > 0:
            self.credit_system._add_reward(node, reward_type or "manual", amount)
        else:
            return web.json_response({"error": "type must be models|gpu|uptime|memory|reputation, or specify amount"}, status=400)

        self.log_event("credits", f"Reward: {reward_type} for {node}")
        return web.json_response({"status": "rewarded", "account": self.credit_system.get_account_info(node)})

    # --- Model endpoints ---

    async def handle_models_list(self, request: web.Request) -> web.Response:
        """GET /api/models — All available models (local + mesh), with availability."""
        models = []
        for model_name in self.local_models:
            provider_name = self._model_provider_map.get(model_name, "unknown")
            provider = self.providers.get(provider_name)
            models.append({
                "name": model_name,
                "source": "local",
                "provider": provider_name,
                "provider_type": provider.provider_type if provider else "unknown",
                "available": True,
                "shared": model_name in self.config.get("public_mesh", {}).get("models_share", []),
                "latency_ms": 0
            })
        for peer in self.peers:
            if peer.available:
                for model_name in peer.models:
                    if model_name not in self.local_models:
                        models.append({
                            "name": model_name,
                            "source": "mesh",
                            "provider": "peer",
                            "peer_name": peer.name,
                            "peer_host": peer.host,
                            "available": peer.available,
                            "shared": False,
                            "latency_ms": peer.avg_latency
                        })
        return web.json_response({"models": models})

    async def handle_model_share(self, request: web.Request) -> web.Response:
        """POST /api/models/{name}/share — Share a model with the mesh."""
        model_name = request.match_info['name']
        if not ALLOWED_MODEL_PATTERN.match(model_name):
            return web.json_response({"error": "invalid model name"}, status=400)
        if model_name not in self.local_models:
            return web.json_response({"error": f"model '{model_name}' not found locally"}, status=404)

        mesh_config = self.config.setdefault("public_mesh", {})
        shared_list = mesh_config.setdefault("models_share", [])
        if model_name not in shared_list:
            shared_list.append(model_name)
            self._persist_config()

        # Use ModelShareManager if available
        if self.model_share_manager:
            try:
                self.model_share_manager.share_model(model_name)
                self.log_event("model_share", f"Model '{model_name}' shared via ModelShareManager")
            except Exception as e:
                self.log_event("model_share", f"ModelShareManager error: {e}", "warn")
        else:
            # Fallback: direct symlink
            shared_dir = Path.home() / ".pinkybrain" / "shared_models"
            shared_dir.mkdir(parents=True, exist_ok=True)
            link_path = shared_dir / model_name.replace(':', '_').replace('/', '_')
            ollama_model_path = Path.home() / ".ollama" / "models" / model_name.replace(':', '/')
            if ollama_model_path.exists() and not link_path.exists():
                try:
                    link_path.symlink_to(ollama_model_path)
                except OSError:
                    pass

        self.log_event("model_share", f"Model '{model_name}' now shared with mesh")
        return web.json_response({"shared": model_name, "models_share": shared_list})

    async def handle_model_unshare(self, request: web.Request) -> web.Response:
        """POST /api/models/{name}/unshare — Stop sharing a model."""
        model_name = request.match_info['name']
        if not ALLOWED_MODEL_PATTERN.match(model_name):
            return web.json_response({"error": "invalid model name"}, status=400)

        mesh_config = self.config.get("public_mesh", {})
        shared_list = mesh_config.get("models_share", [])
        if model_name in shared_list:
            shared_list.remove(model_name)
            self._persist_config()

        # Use ModelShareManager if available
        if self.model_share_manager:
            try:
                self.model_share_manager.unshare_model(model_name)
                self.log_event("model_unshare", f"Model '{model_name}' unshared via ModelShareManager")
            except Exception as e:
                self.log_event("model_unshare", f"ModelShareManager error: {e}", "warn")
        else:
            # Fallback: remove symlink
            link_name = model_name.replace(':', '_').replace('/', '_')
            link_path = Path.home() / ".pinkybrain" / "shared_models" / link_name
            if link_path.is_symlink():
                try:
                    link_path.unlink()
                except OSError:
                    pass

        self.log_event("model_unshare", f"Model '{model_name}' unshared from mesh")
        return web.json_response({"unshared": model_name, "models_share": shared_list})

    # --- v5.2: Model Registry endpoints ---

    async def handle_registry_list(self, request: web.Request) -> web.Response:
        """GET /api/registry — Lister les modèles du catalogue avec filtres."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        source = request.query.get("source")
        category = request.query.get("category")
        tag = request.query.get("tag")
        language = request.query.get("language")
        try:
            min_quality = int(request.query.get("min_quality", "0"))
        except (ValueError, TypeError):
            min_quality = None
        shared_only = request.query.get("shared", "").lower() == "true"
        available_only = request.query.get("available", "").lower() == "true"
        downloadable = request.query.get("downloadable", "").lower() == "true"
        sort_by = request.query.get("sort", "quality")
        models = self.model_registry.list_models(
            source=source, category=category, tag=tag,
            language=language, min_quality=min_quality or None,
            shared_only=shared_only, available_only=available_only,
            downloadable_only=downloadable, sort_by=sort_by,
        )
        return web.json_response({
            "models": [m.to_dict() for m in models],
            "total": len(models),
            "filters": {
                "source": source, "category": category, "tag": tag,
                "language": language, "min_quality": min_quality,
                "shared_only": shared_only, "available_only": available_only,
                "downloadable_only": downloadable, "sort_by": sort_by,
            }
        })

    async def handle_registry_stats(self, request: web.Request) -> web.Response:
        """GET /api/registry/stats — Statistiques du registre."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        stats = self.model_registry.get_stats()
        return web.json_response(stats)

    async def handle_registry_info(self, request: web.Request) -> web.Response:
        """GET /api/registry/{name} — Fiche détaillée d'un modèle."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        name = request.match_info['name']
        card = self.model_registry.get_model(name)
        if not card:
            # Try URL-decoded name
            from urllib.parse import unquote
            name = unquote(name)
            card = self.model_registry.get_model(name)
        if not card:
            # Fuzzy search
            results = self.model_registry.search(name)
            if results:
                card = results[0]
            else:
                return web.json_response({"error": f"Model '{name}' not found"}, status=404)
        return web.json_response(card.to_dict())

    async def handle_registry_add(self, request: web.Request) -> web.Response:
        """POST /api/registry — Ajouter un modèle au registre.

        Body: {
            "name": "model-name",
            "display_name": "Model Name",
            "description": "...",
            "source": "local|cloud|wishlist|mesh",
            "categories": ["code", "reasoning"],
            "quality_rating": 7,
            "speed_rating": 8,
            "context_window": 32768,
            "size_category": "small",
            "params_count": "8B",
            "ram_required_gb": 8,
            "vram_required_gb": 0,
            "strengths": ["..."],
            "limitations": ["..."],
            "best_for": ["..."],
            "not_for": ["..."],
            "languages": ["en", "fr"],
            "provider": "ollama",
            "license": "...",
            "notes": "..."
        }
        """
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        data = await request.json()
        name = data.get("name", "").strip()
        if not name:
            return web.json_response({"error": "name is required"}, status=400)
        try:
            source = ModelSource(data.get("source", "local"))
        except ValueError:
            source = ModelSource.LOCAL
        try:
            status = ModelStatus(data.get("status", "ready"))
        except ValueError:
            status = ModelStatus.READY
        card = ModelCard(
            name=name,
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            long_description=data.get("long_description", ""),
            source=source,
            status=status,
            categories=data.get("categories", []),
            tags=data.get("tags", []),
            quality_rating=int(data.get("quality_rating", 5)),
            speed_rating=int(data.get("speed_rating", 5)),
            context_window=int(data.get("context_window", 8192)),
            size_category=data.get("size_category", "small"),
            params_count=data.get("params_count", ""),
            ram_required_gb=float(data.get("ram_required_gb", 4)),
            vram_required_gb=float(data.get("vram_required_gb", 0)),
            disk_size_gb=float(data.get("disk_size_gb", 0)),
            strengths=data.get("strengths", []),
            limitations=data.get("limitations", []),
            best_for=data.get("best_for", []),
            not_for=data.get("not_for", []),
            languages=data.get("languages", ["en"]),
            primary_language=data.get("primary_language", "en"),
            provider=data.get("provider", "ollama"),
            architecture=data.get("architecture", ""),
            license=data.get("license", ""),
            quantization=data.get("quantization", ""),
            price_per_million_input=float(data.get("price_per_million_input", 0)),
            price_per_million_output=float(data.get("price_per_million_output", 0)),
            notes=data.get("notes", ""),
        )
        self.model_registry.add_model(card)
        self.log_event("registry_add", f"Model '{name}' added to registry ({source.value})")
        return web.json_response({"added": card.to_dict()}, status=201)

    async def handle_registry_remove(self, request: web.Request) -> web.Response:
        """DELETE /api/registry/{name} — Supprimer un modèle du registre."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        name = request.match_info['name']
        if self.model_registry.remove_model(name):
            self.log_event("registry_remove", f"Model '{name}' removed from registry")
            return web.json_response({"removed": name})
        return web.json_response({"error": f"Model '{name}' not found"}, status=404)

    async def handle_registry_update(self, request: web.Request) -> web.Response:
        """PUT /api/registry/{name} — Mettre à jour un modèle."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        name = request.match_info['name']
        data = await request.json()
        if self.model_registry.update_model(name, data):
            card = self.model_registry.get_model(name)
            self.log_event("registry_update", f"Model '{name}' updated")
            return web.json_response(card.to_dict())
        return web.json_response({"error": f"Model '{name}' not found"}, status=404)

    async def handle_registry_search(self, request: web.Request) -> web.Response:
        """GET /api/registry/search/{query} — Rechercher des modèles."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        query = request.match_info.get('query', '')
        from urllib.parse import unquote
        query = unquote(query)
        results = self.model_registry.search(query)
        return web.json_response({
            "query": query,
            "results": [m.to_dict() for m in results],
            "total": len(results),
        })

    async def handle_registry_recommend(self, request: web.Request) -> web.Response:
        """GET /api/registry/recommend — Recommandations personnalisées.

        Query params: task, language, max_ram_gb, min_quality
        """
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        task = request.query.get("task")
        language = request.query.get("language", "fr")
        try:
            max_ram = float(request.query.get("max_ram_gb", "0"))
        except (ValueError, TypeError):
            max_ram = None
        try:
            min_q = int(request.query.get("min_quality", "0"))
        except (ValueError, TypeError):
            min_q = None
        recs = self.model_registry.get_recommendations(
            task=task, language=language,
            max_ram_gb=max_ram if max_ram and max_ram > 0 else None,
            min_quality=min_q if min_q and min_q > 0 else None,
        )
        return web.json_response({
            "recommendations": [m.to_dict() for m in recs[:10]],
            "total": len(recs),
            "params": {"task": task, "language": language, "max_ram_gb": max_ram, "min_quality": min_q},
        })

    async def handle_registry_mesh(self, request: web.Request) -> web.Response:
        """GET /api/registry/mesh — Catalogue des modèles disponibles sur le mesh public."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        mesh_models = self.model_registry.get_mesh_catalog()
        return web.json_response({
            "mesh_catalog": [m.to_dict() for m in mesh_models],
            "total": len(mesh_models),
        })

    async def handle_registry_wishlist(self, request: web.Request) -> web.Response:
        """GET /api/registry/wishlist — Liste des modèles souhaités."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        wishlist = self.model_registry.get_wishlist()
        return web.json_response({
            "wishlist": [m.to_dict() for m in wishlist],
            "total": len(wishlist),
        })

    async def handle_registry_wishlist_add(self, request: web.Request) -> web.Response:
        """POST /api/registry/wishlist/{name} — Ajouter un modèle à la wishlist."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        name = request.match_info['name']
        data = await request.json() if request.content_type == 'application/json' else {}
        notes = data.get("notes", "") if isinstance(data, dict) else ""
        card = self.model_registry.add_to_wishlist(name, notes=notes)
        self.log_event("registry_wishlist", f"Model '{name}' added to wishlist")
        return web.json_response({"wishlist": card.to_dict()}, status=201)

    async def handle_registry_share(self, request: web.Request) -> web.Response:
        """POST /api/registry/{name}/share — Marquer un modèle comme partagé dans le registre.
        
        Par défaut, les modèles cloud et wishlist ne sont PAS partageables.
        Utiliser ?force=true pour forcer le partage d'un modèle cloud (à vos risques).
        
        ⚠️ ATTENTION : partager un modèle cloud sur le mesh public signifie que
        d'autres nœuds peuvent rediriger des requêtes vers VOTRE clé API. Vous êtes
        responsable de l'usage et des coûts générés. Le programme de raid/share prend
        tout son sens quand plusieurs utilisateurs partagent leurs ressources cloud,
        mais chacun le fait à ses propres risques.
        """
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        name = request.match_info['name']
        force = request.query.get("force", "false").lower() == "true"
        
        # Vérifier le type de modèle avant de partager
        card = self.model_registry.get_model(name)
        if not card:
            return web.json_response({"error": f"Model '{name}' not found"}, status=404)
        
        # Avertissement si c'est un modèle cloud
        is_cloud = card.source.value == "cloud" or name.endswith(":cloud") or ":cloud:" in name
        if is_cloud and not force:
            return web.json_response({
                "error": f"Cloud model '{name}' cannot be shared on the public mesh by default",
                "reason": "cloud_private_by_default",
                "model": name,
                "source": card.source.value,
                "warning": "Sharing a cloud model means other nodes will route requests through YOUR API key. You are responsible for usage and costs.",
                "hint": "Add ?force=true to override this policy at your own risk"
            }, status=403)
        
        if self.model_registry.share_model(name, force=force):
            log_msg = f"Model '{name}' shared on mesh"
            if is_cloud and force:
                log_msg += " (CLOUD MODEL — user acknowledged risk)"
            self.log_event("registry_share", log_msg)
            response = {"shared": name, "source": card.source.value}
            if is_cloud:
                response["warning"] = "You are sharing a cloud model on the public mesh. Other nodes will use YOUR API key. You are responsible for all costs incurred."
                response["risk_acknowledged"] = True
            return web.json_response(response)
        return web.json_response({"error": f"Model '{name}' cannot be shared"}, status=400)

    async def handle_registry_unshare(self, request: web.Request) -> web.Response:
        """POST /api/registry/{name}/unshare — Arrêter le partage d'un modèle dans le registre."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        name = request.match_info['name']
        if self.model_registry.unshare_model(name):
            self.log_event("registry_unshare", f"Model '{name}' unshared in registry")
            return web.json_response({"unshared": name})
        return web.json_response({"error": f"Model '{name}' not found"}, status=404)

    async def handle_registry_purge(self, request: web.Request) -> web.Response:
        """POST /api/registry/purge — Purger les modèles mesh sans nœud actif depuis > 12 mois."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        try:
            max_age_days = int(request.query.get("max_age_days", "365"))
        except (ValueError, TypeError):
            max_age_days = 365
        purged = self.model_registry.purge_stale_models(max_age_days=max_age_days)
        purged_names = [p.name for p in purged]
        if purged_names:
            self.log_event("registry_purge", f"Purged {len(purged_names)} stale mesh models: {purged_names}")
        return web.json_response({
            "purged": purged_names,
            "count": len(purged_names),
            "max_age_days": max_age_days,
            "message": f"Purged {len(purged_names)} mesh models not seen in {max_age_days}+ days"
        })

    async def handle_registry_stale(self, request: web.Request) -> web.Response:
        """GET /api/registry/stale — Vérifier les modèles proches de l'obsolescence."""
        if not self.model_registry:
            return web.json_response({"error": "Model Registry not available"}, status=501)
        try:
            max_age_days = int(request.query.get("max_age_days", "365"))
        except (ValueError, TypeError):
            max_age_days = 365
        stale = self.model_registry.check_stale_models(max_age_days=max_age_days)
        return web.json_response({
            "stale": stale,
            "count": len(stale),
            "threshold_days": max_age_days,
        })

    # --- Network endpoints ---

    async def handle_network_sync_status(self, request: web.Request) -> web.Response:
        """GET /api/network/sync — Statut de la synchronisation réseau."""
        if not self.network_sync:
            return web.json_response({"error": "NetworkSync not available"}, status=501)
        status = self.network_sync.get_sync_status()
        # Ajouter le rapport des modèles manquants
        status["missing_models"] = self.network_sync._find_missing_models() if self.model_registry else []
        return web.json_response(status)

    async def handle_network_sync_run(self, request: web.Request) -> web.Response:
        """POST /api/network/sync — Lancer une synchronisation manuelle."""
        if not self.network_sync:
            return web.json_response({"error": "NetworkSync not available"}, status=501)
        results = await self.network_sync.full_sync()
        self.log_event("network_sync", f"Manual sync: {results}")
        return web.json_response(results)

    async def handle_dns_list(self, request: web.Request) -> web.Response:
        """GET /api/network/dns — Liste des nœuds du DNS dynamique.
        
        Query params:
            active_only: bool — ne retourner que les nœuds actifs (défaut: true)
            max_age_days: float — âge max en jours (défaut: 30)
        """
        if not self.network_sync:
            return web.json_response({"error": "NetworkSync not available"}, status=501)
        active_only = request.query.get("active_only", "true").lower() == "true"
        try:
            max_age_days = float(request.query.get("max_age_days", str(NODE_STALE_THRESHOLD_DAYS)))
        except (ValueError, TypeError):
            max_age_days = NODE_STALE_THRESHOLD_DAYS
        if active_only:
            nodes = self.network_sync.dns.get_active_nodes(max_age_days=max_age_days)
        else:
            nodes = list(self.network_sync.dns._nodes.values())
        return web.json_response({
            "nodes": nodes,
            "total": len(nodes),
            "active_only": active_only,
            "max_age_days": max_age_days,
        })

    async def handle_dns_stats(self, request: web.Request) -> web.Response:
        """GET /api/network/dns/stats — Statistiques du DNS dynamique."""
        if not self.network_sync:
            return web.json_response({"error": "NetworkSync not available"}, status=501)
        return web.json_response(self.network_sync.dns.get_stats())

    async def handle_missing_models(self, request: web.Request) -> web.Response:
        """GET /api/network/missing — Modèles disponibles sur le mesh mais pas locaux."""
        if not self.network_sync:
            return web.json_response({"error": "NetworkSync not available"}, status=501)
        missing = self.network_sync._find_missing_models()
        return web.json_response({
            "missing_models": missing,
            "count": len(missing),
            "message": f"{len(missing)} model(s) available on mesh but not in local catalog",
        })

    async def handle_network_private_peers(self, request: web.Request) -> web.Response:
        """GET /api/network/private/peers — List private network peers."""
        peers_list = []
        for p in self.peers:
            peers_list.append({
                "name": p.name,
                "host": p.host,
                "port": p.port,
                "available": p.available,
                "models": p.models,
                "last_seen": p.last_seen,
                "avg_latency_ms": p.avg_latency,
                "public_key": p.public_key_hex[:16] + "..." if p.public_key_hex else None
            })
        return web.json_response({
            "network": "private", "auth": "p2p_secret",
            "peers": peers_list, "total": len(peers_list),
            "available": sum(1 for p in self.peers if p.available)
        })

    async def handle_network_mesh_nodes(self, request: web.Request) -> web.Response:
        """GET /api/network/mesh/nodes — List public mesh nodes."""
        mesh_config = self.config.get("public_mesh", {})
        if not mesh_config.get("enabled", False):
            return web.json_response({
                "mesh_enabled": False, "nodes": [], "total": 0,
                "message": "Public mesh is not enabled"
            })
        mesh_nodes = []
        zc_peers = self.zero_config.get_discovered_peers()
        for p in zc_peers:
            mesh_nodes.append({
                "name": p.get("name", "unknown"),
                "address": p.get("host", ""),
                "port": p.get("port", 8090),
                "capabilities": p.get("capabilities", {}),
                "score": p.get("score", 0)
            })
        return web.json_response({
            "mesh_enabled": True,
            "tracker_url": mesh_config.get("tracker_url", ""),
            "nodes": mesh_nodes, "total": len(mesh_nodes)
        })

    async def handle_network_mesh_join(self, request: web.Request) -> web.Response:
        """POST /api/network/mesh/join — Join the public mesh."""
        mesh_config = self.config.setdefault("public_mesh", {})
        mesh_config["enabled"] = True
        self._persist_config()
        if not self.zero_config._running:
            await self.zero_config.start()
        self.log_event("mesh", "Joined public mesh")
        return web.json_response({
            "status": "joined", "mesh_enabled": True,
            "tracker_url": mesh_config.get("tracker_url", "")
        })

    async def handle_network_mesh_leave(self, request: web.Request) -> web.Response:
        """POST /api/network/mesh/leave — Leave the public mesh."""
        mesh_config = self.config.setdefault("public_mesh", {})
        mesh_config["enabled"] = False
        self._persist_config()
        if self.zero_config._running:
            await self.zero_config.stop()
        self.log_event("mesh", "Left public mesh")
        return web.json_response({"status": "left", "mesh_enabled": False})

    # --- Model Networks endpoints (v5.2) ---

    async def handle_model_networks_get(self, request: web.Request) -> web.Response:
        """GET /api/model-networks — Get current model network configuration.
        Returns private networks list and model permissions matrix.
        Secrets are masked for security.
        """
        networks = self.model_networks.get("private_networks", [])
        permissions = self.model_networks.get("model_permissions", {})

        # Mask secrets in response
        masked_networks = []
        for net in networks:
            masked_net = {"id": net["id"], "name": net["name"], "secret": "***" if net.get("secret") else ""}
            masked_networks.append(masked_net)

        return web.json_response({
            "private_networks": masked_networks,
            "model_permissions": permissions,
            "local_models": self.local_models
        })

    async def handle_model_networks_save(self, request: web.Request) -> web.Response:
        """POST /api/model-networks — Save model network configuration.
        Accepts: private_networks (list of {id, name, secret}),
             model_permissions (dict of model_name -> {share_private: [ids], use_private: [ids], share_public: bool, use_public: bool})
        """
        data = await request.json()

        # Validate private_networks
        private_networks = data.get("private_networks")
        if private_networks is not None:
            if not isinstance(private_networks, list):
                return web.json_response({"error": "private_networks must be a list"}, status=400)
            for net in private_networks:
                if not isinstance(net, dict) or "id" not in net or "name" not in net:
                    return web.json_response({"error": "Each network must have id and name"}, status=400)
                net["id"] = int(net["id"])
                net["name"] = str(net["name"])[:64]  # max 64 chars
                # Generate secret if empty
                if not net.get("secret") or net["secret"] == "***":
                    # Keep existing secret if we're just updating name
                    existing = [n for n in self.model_networks.get("private_networks", []) if n["id"] == net["id"]]
                    if existing and existing[0].get("secret"):
                        net["secret"] = existing[0]["secret"]
                    else:
                        import secrets as _secrets
                        net["secret"] = _secrets.token_hex(32)
                net["secret"] = str(net["secret"])[:128]  # max 128 chars
            self.model_networks["private_networks"] = private_networks

        # Validate model_permissions
        model_permissions = data.get("model_permissions")
        if model_permissions is not None:
            if not isinstance(model_permissions, dict):
                return web.json_response({"error": "model_permissions must be a dict"}, status=400)
            # Validate each model's permissions
            valid_network_ids = {n["id"] for n in self.model_networks.get("private_networks", [])}
            cleaned = {}
            for model_name, perms in model_permissions.items():
                if not ALLOWED_MODEL_PATTERN.match(model_name):
                    continue  # skip invalid model names
                if not isinstance(perms, dict):
                    continue
                cleaned_perms = {}
                for key in ("share_private", "use_private", "share_public", "use_public"):
                    if key in perms:
                        if key.endswith("_public"):
                            cleaned_perms[key] = bool(perms[key])
                        else:
                            # List of network IDs
                            val = perms[key]
                            if isinstance(val, list):
                                cleaned_perms[key] = [int(v) for v in val if int(v) in valid_network_ids]
                            else:
                                cleaned_perms[key] = []
                cleaned[model_name] = cleaned_perms
            self.model_networks["model_permissions"] = cleaned

        self.config["model_networks"] = self.model_networks
        self._persist_config()
        self.log_event("model_networks", "Model network configuration saved")

        # Return masked version
        masked_networks = []
        for net in self.model_networks.get("private_networks", []):
            masked_networks.append({"id": net["id"], "name": net["name"], "secret": "***" if net.get("secret") else ""})

        return web.json_response({
            "status": "saved",
            "private_networks": masked_networks,
            "model_permissions": self.model_networks.get("model_permissions", {})
        })

    async def handle_model_networks_generate_secret(self, request: web.Request) -> web.Response:
        """POST /api/model-networks/{network_id}/generate-secret — Generate a new secret for a private network.
        Returns the new secret (shown once). The stored version is masked.
        """
        network_id = int(request.match_info['network_id'])
        networks = self.model_networks.get("private_networks", [])
        target = None
        for net in networks:
            if net["id"] == network_id:
                target = net
                break
        if not target:
            return web.json_response({"error": f"Network {network_id} not found"}, status=404)

        import secrets as _secrets
        new_secret = _secrets.token_hex(32)
        target["secret"] = new_secret
        self.model_networks["private_networks"] = networks
        self.config["model_networks"] = self.model_networks
        self._persist_config()
        self.log_event("model_networks", f"Generated new secret for network '{target['name']}' (id={network_id})")

        # Return the secret ONCE — it will be masked in subsequent GETs
        return web.json_response({
            "network_id": network_id,
            "network_name": target["name"],
            "secret": new_secret,
            "warning": "Store this secret securely — it will not be shown again via API"
        })

    # --- Config endpoints ---

    SECRET_KEYS = {"p2p_secret", "secret", "password", "token", "api_key", "private_key", "auth_key"}

    def _mask_config(self, cfg: Dict) -> Dict:
        """Recursively mask secrets in a config dict."""
        masked = {}
        for k, v in cfg.items():
            if any(s in k.lower() for s in self.SECRET_KEYS):
                masked[k] = "***MASKED***"
            elif isinstance(v, dict):
                masked[k] = self._mask_config(v)
            else:
                masked[k] = v
        return masked

    async def handle_config_get(self, request: web.Request) -> web.Response:
        """GET /api/config — Current configuration (secrets MASKED)."""
        return web.json_response({"config": self._mask_config(self.config)})

    async def handle_config_set(self, request: web.Request) -> web.Response:
        """POST /api/config — Modify configuration.
        Requires explicit confirmation. Secrets cannot be set via this endpoint.
        """
        data = await request.json()
        updates = data.get("updates", {})
        if not updates:
            return web.json_response({"error": "no updates provided"}, status=400)
        if not data.get("confirm"):
            return web.json_response({
                "error": "Config changes require explicit confirmation",
                "hint": "Set 'confirm': true in your request"
            }, status=400)
        for key in updates:
            if any(s in key.lower() for s in self.SECRET_KEYS):
                return web.json_response({
                    "error": f"Cannot modify '{key}' via API for security reasons"
                }, status=403)
        applied = {}
        for key, value in updates.items():
            if key == "node_name" and not isinstance(value, str):
                return web.json_response({"error": "node_name must be a string"}, status=400)
            if key == "stealth_mode" and not isinstance(value, bool):
                return web.json_response({"error": "stealth_mode must be a boolean"}, status=400)
            if key == "share_ai" and not isinstance(value, bool):
                return web.json_response({"error": "share_ai must be a boolean"}, status=400)
            self.config[key] = value
            applied[key] = value
        self._persist_config()
        if "stealth_mode" in applied:
            self.stealth_mode = self.config["stealth_mode"]
        if "share_ai" in applied:
            self.share_ai = self.config["share_ai"]
        self.log_event("config", f"Config updated: {list(applied.keys())}")
        return web.json_response({"status": "updated", "applied": self._mask_config(applied)})

    def _persist_config(self):
        """Save current config to disk."""
        try:
            config_dir = Path.home() / ".pinkybrain" / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / f"{self.node_name}.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"Config persisted to {config_path}")
        except OSError as e:
            logger.error(f"Failed to persist config: {e}")


    # ========================================================================

    # Specialist endpoints
    # ========================================================================

    async def handle_specialties_list(self, request: web.Request) -> web.Response:
        """GET /api/specialties — List all available specialties and their models."""
        if not self.specialist_router:
            return web.json_response({"error": "Specialist routing not available"}, status=501)
        specialties = self.specialist_router.get_all_specialties()
        return web.json_response({
            "specialties": specialties,
            "available_models": self.local_models,
            "registered_profiles": list(self.specialist_router._profiles.keys()),
        })

    async def handle_specialty_models(self, request: web.Request) -> web.Response:
        """GET /api/specialties/{name}/models — List models for a specific specialty."""
        if not self.specialist_router:
            return web.json_response({"error": "Specialist routing not available"}, status=501)
        name = request.match_info.get('name', '')
        try:
            specialty = ModelSpecialty(name)
        except ValueError:
            valid = [s.value for s in ModelSpecialty]
            return web.json_response({
                "error": f"Unknown specialty '{name}'",
                "valid_specialties": valid
            }, status=400)
        models = self.specialist_router.get_specialty_models(specialty)
        return web.json_response({
            "specialty": name,
            "models": models,
        })

    async def handle_multi_model_query(self, request: web.Request) -> web.Response:
        """POST /api/multi — Multi-model query with fusion strategies.
        
        Body: {
            "prompt": "...",
            "models": ["model1", "model2"],  // optional: force specific models
            "specialties": ["code", "reasoning"],  // optional: select by specialties
            "mode": "vote",  // single, vote, chain, fuse, compare, specialist
            "strategy": "auto"  // underlying query strategy
        }
        """
        if not self.specialist_router or not self.multi_model_executor:
            return web.json_response({"error": "Specialist routing not available"}, status=501)

        data = await request.json()
        prompt = data.get("prompt", "")
        mode_name = data.get("mode", "specialist")
        models_param = data.get("models")
        specialties_param = data.get("specialties")
        strategy = data.get("strategy", "auto")

        if not prompt or len(prompt) > MAX_PROMPT_LENGTH:
            return web.json_response(
                {"error": f"prompt must be 1-{MAX_PROMPT_LENGTH} characters"}, status=400)

        # Parse mode
        try:
            mode = MultiModelMode(mode_name)
        except ValueError:
            valid = [m.value for m in MultiModelMode]
            return web.json_response({
                "error": f"Unknown mode '{mode_name}'",
                "valid_modes": valid
            }, status=400)

        # Determine which models to use
        if models_param:
            selected = self.specialist_router.select_models_by_names(models_param)
        elif specialties_param:
            specs = []
            for s in specialties_param:
                try:
                    specs.append(ModelSpecialty(s))
                except ValueError:
                    pass
            selected = self.specialist_router.select_models_for_specialties(specs, self.local_models)
        else:
            # Auto-detect from prompt
            routing = self.specialist_router.route(prompt, available=self.local_models)
            selected = routing["models"]

        if not selected:
            selected = self.local_models[:1] if self.local_models else []

        if not selected:
            return web.json_response({"error": "No models available"}, status=503)

        # Execute multi-model query
        async def _query_one(model: str, p: str) -> dict:
            return await self.query(p, model, strategy)

        result = await self.multi_model_executor.execute(
            prompt, selected, mode, query_fn=_query_one
        )

        return web.json_response(result.to_dict())

    # ========================================================================

    async def handle_capabilities(self, request: web.Request) -> web.Response:
        """Return this node's hardware capabilities and peer capabilities."""
        peer_caps = {name: caps.to_dict() for name, caps in self.model_negotiator.peer_caps.items()}
        return web.json_response({
            "own": self.own_capabilities.to_dict(),
            "peers": peer_caps
        })

    async def handle_gamified_score(self, request: web.Request) -> web.Response:
        """Return gamified score tier for a peer."""
        peer_name = request.match_info['peer']
        score = self.sharing_quota.calculate_score(peer_name)
        tier = GamifiedScore.get_tier(score)
        return web.json_response(tier)

    async def handle_discover(self, request: web.Request) -> web.Response:
        """Return zero-config discovered peers."""
        peers = self.zero_config.get_discovered_peers()
        return web.json_response({
            "discovered_peers": peers,
            "count": len(peers)
        })

    async def handle_update_check(self, request: web.Request) -> web.Response:
        """Check for PinkyBrain updates."""
        update = await self.auto_updater.check()
        if update:
            return web.json_response({"update_available": True, **update})
        return web.json_response({"update_available": False, "current": AutoUpdater.CURRENT_VERSION})

    async def handle_daemon_status(self, request: web.Request) -> web.Response:
        """Return daemon/systray status."""
        return web.json_response(self.systray.status())

    async def handle_agent_sidekick(self, request: web.Request) -> web.Response:
        """Sidekick endpoint for OpenClaw agents.
        
        HIGH-03 fix: Require auth for full info; return minimal info for unauthenticated.
        """
        auth = self._verify_auth(request)
        if auth is None:
            # Minimal public info only
            return web.json_response({
                'sidekick': True,
                'version': self.version,
                'node_name': self.node_name,
                'status': 'online',
            })
        status = self.get_status()
        caps = self.own_capabilities.to_dict()
        all_models = list(self.local_models)
        for p in self.peers:
            all_models.extend([m for m in p.models if m not in all_models])
        
        own_score = self.sharing_quota.calculate_score(self.node_name)
        tier = GamifiedScore.get_tier(own_score)
        
        return web.json_response({
            'sidekick': True,
            'version': self.version,
            'node_name': self.node_name,
            'status': 'online',
            'models': {
                'local': self.local_models,
                'peers': {p.name: p.models for p in self.peers if p.available},
                'all': all_models,
                'total': len(all_models)
            },
            'capabilities': caps,
            'score': tier,
            'peers_online': sum(1 for p in self.peers if p.available),
            'peers_total': len(self.peers),
            'zero_config_peers': len(self.zero_config.get_discovered_peers()),
            'memory_keys': len(self.memory.store),
            'query_url': f'http://{self.host}:{self.port}/api/query',
            'memory_url': f'http://{self.host}:{self.port}/api/memory',
            'capabilities_url': f'http://{self.host}:{self.port}/api/capabilities',
        })

    async def handle_agent_query(self, request: web.Request) -> web.Response:
        """Sidekick query endpoint for OpenClaw agents.
        
        Accepts: {"prompt": "...", "model": "..."}
        Routes through GPU/CPU negotiation if available.
        """
        try:
            data = await request.json()
            prompt = data.get('prompt', '')
            model = data.get('model')
            
            if not prompt:
                return web.json_response({'error': 'prompt required'}, status=400)
            
            # Use model negotiation to find best node
            if model:
                routing = self.router.route_with_capabilities(
                    model, self.local_models, self.peers
                )
                target = routing['target']
                
                # If local, query directly
                if target == 'local':
                    result = await self._query_local(model, prompt)
                    return web.json_response({
                        'model': model,
                        'target': 'local',
                        'result': result,
                        'routed_by': 'capabilities'
                    })
                
                # If peer, query the peer
                peer = next((p for p in self.peers if p.name == target), None)
                if peer and peer.available:
                    result = await self._query_peer(peer, model, prompt)
                    return web.json_response({
                        'model': model,
                        'target': target,
                        'result': result,
                        'routed_by': 'capabilities'
                    })
            
            # Fallback: normal query flow
            result = await self.query(prompt, model)
            return web.json_response(result)
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    # FEATURE 1: WEBSOCKET TEMPS RÉEL
    # ========================================================================

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=self.heartbeat_interval, max_msg_size=WS_MAX_MSG_SIZE)  # LOW-07: Limit WS message size
        await ws.prepare(request)

        client_id = str(uuid.uuid4())[:8]
        # HIGH-02 fix: Don't add to ws_clients until authenticated
        # Track as pending; only promote to ws_clients after auth
        pending = True
        auth_deadline = time.time() + AUTH_TIMEOUT_SECONDS
        self.log_event("ws", f"WS pending auth {client_id} from {request.remote}")

        # Stealth mode: reject unknown nodes
        if self.stealth_mode and not self._stealth_check(request):
            await ws.send_json({'type': 'error', 'message': 'Node not recognized'})
            await ws.close()
            return ws

        try:
            async for msg in ws:
                # HIGH-02 fix: Enforce auth timeout
                if pending and time.time() > auth_deadline:
                    await ws.send_json({'type': 'error', 'message': 'Authentication timeout'})
                    await ws.close()
                    break
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    msg_type = data.get('type', '')

                    # Auth via WS
                    if msg_type == 'auth':
                        authenticated = await self._ws_authenticate(data, ws, client_id)
                        if authenticated:
                            self.ws_authenticated.add(client_id)
                            # HIGH-02 fix: Only add to ws_clients after successful auth
                            self.ws_clients[client_id] = ws
                            pending = False
                            self.log_event("ws", f"WS authenticated {client_id} from {request.remote} ({len(self.ws_clients)} total)")
                        continue

                    # HIGH-02 fix: Require auth for ALL operations (not just writes)
                    if client_id not in self.ws_authenticated:
                        await ws.send_json({'type': 'error', 'message': 'Authentication required'})
                        continue

                    # Typed message handlers
                    if msg_type == 'ping':
                        await ws.send_json({'type': 'pong', 'node': self.node_name,
                                            'version': self.version, 'time': time.time()})
                    elif msg_type == 'query':
                        result = await self.query(data.get('prompt', ''), data.get('model'))
                        await ws.send_json({'type': 'query_result', **result})
                    elif msg_type == 'memory_sync':
                        entries = data.get('entries', {})
                        merged = self.memory.merge_from_sync(entries)
                        await ws.send_json({'type': 'sync_ack', 'keys_merged': merged})
                        self.log_event("ws_sync", f"Merged {merged} entries via WS")
                    elif msg_type == 'memory_update':
                        key = data.get('key', '')
                        entry = data.get('entry', {})
                        if key and entry:
                            merged = self.memory.merge_from_sync({key: entry})
                            # Gossip to other clients
                            await self._broadcast_ws({
                                'type': 'memory_update', 'key': key, 'entry': entry
                            }, exclude=client_id)
                    elif msg_type == 'memory_request':
                        vc = data.get('vector_clock', {})
                        if vc:
                            delta = self.memory.get_delta_since(vc)
                            await ws.send_json({'type': 'memory_delta', 'entries': delta})
                        else:
                            entries = self.memory.get_all_for_sync()
                            await ws.send_json({'type': 'memory_full', 'entries': entries})
                    elif msg_type == 'notification':
                        # Broadcast notification to all WS clients (with gossip propagation)
                        gossip_msg = {
                            'type': 'notification',
                            'message': data.get('message', ''),
                            'source': data.get('source', self.node_name),
                            'msg_id': data.get('msg_id', f"{self.node_name}:{uuid.uuid4().hex[:8]}"),
                            'timestamp': time.time()
                        }
                        await self._gossip_propagate(gossip_msg)
                    elif msg_type == 'peer_discovery':
                        # Node announces itself
                        peer_info = data.get('peer', {})
                        peer_key = data.get('public_key', '')
                        self.log_event("ws_discover", f"Peer {peer_info.get('name', '?')} via WS")
                        await ws.send_json({
                            'type': 'discover_ack',
                            'node': self.node_name,
                            'models': self.local_models,
                            'public_key': self.identity.public_key_hex,
                            'peers': [p.to_dict() for p in self.peers]
                        })
                    elif msg_type == 'status':
                        await ws.send_json({'type': 'status', **self.get_status()})

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WS error: {ws.exception()}')

        except (aiohttp.ServerDisconnectedError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            self.ws_clients.pop(client_id, None)
            self.ws_authenticated.discard(client_id)
            self.log_event("ws", f"WS disconnected {client_id} ({len(self.ws_clients)} total)")
        return ws

    async def _ws_authenticate(self, data: Dict, ws: web.WebSocketResponse,
                                client_id: str) -> bool:
        """Authenticate a WS client via Ed25519 challenge-response or shared secret."""
        # Ed25519 challenge-response
        if data.get('response') and data.get('from_key'):
            challenge = data.get('challenge', '')
            if self.identity.verify(challenge, data['response'], data['from_key']):
                await ws.send_json({'type': 'auth_ack', 'status': 'ok',
                                     'node': self.node_name,
                                     'public_key': self.identity.public_key_hex})
                return True

        # Shared secret HMAC
        hmac_sig = data.get('hmac', '')
        hmac_ts = data.get('ts', '')
        if hmac_sig and hmac_ts:
            # NEW-03: Verify timestamp window for WS auth HMAC too
            try:
                if abs(time.time() - float(hmac_ts)) > HMAC_WINDOW_SECONDS:
                    await ws.send_json({'type': 'auth_ack', 'status': 'failed', 'reason': 'expired'})
                    return False
            except ValueError:
                await ws.send_json({'type': 'auth_ack', 'status': 'failed', 'reason': 'invalid timestamp'})
                return False
            # NEW-01: Nonce check for WS auth
            ws_nonce = f"ws-hmac:{hmac_ts}"
            if not self._check_and_add_nonce(ws_nonce):
                await ws.send_json({'type': 'auth_ack', 'status': 'failed', 'reason': 'replay'})
                return False
            import hmac as hmac_mod
            msg_str = f"/ws:{hmac_ts}"
            expected_sig = hmac_mod.new(
                self.p2p_secret.encode(), msg_str.encode(), hashlib.sha256).hexdigest()
            if hmac_mod.compare_digest(hmac_sig, expected_sig):
                await ws.send_json({'type': 'auth_ack', 'status': 'ok'})
                return True

        await ws.send_json({'type': 'auth_ack', 'status': 'failed'})
        return False

    async def _broadcast_ws(self, data: Dict, exclude: str = None):
        """Broadcast data to all authenticated WS clients except excluded one."""
        msg = json.dumps(data)
        dead = []
        for cid, client in list(self.ws_clients.items()):
            if cid == exclude:
                continue
            # Only broadcast to authenticated clients
            if cid not in self.ws_authenticated:
                continue
            if client.closed:
                dead.append(cid)
                continue
            try:
                await client.send_str(msg)
            except ConnectionResetError:
                dead.append(cid)
        for cid in dead:
            self.ws_clients.pop(cid, None)
            self.ws_authenticated.discard(cid)

    # ========================================================================
    # FEATURE 3: GOSSIP PROTOCOL
    # ========================================================================

    async def _gossip_broadcast(self, message: Dict):
        """Broadcast a message via gossip to all connected WS peers and known HTTP peers.
        Bug #1 fix: send correct payload based on message type."""
        msg_id = f"{self.node_name}:{uuid.uuid4().hex[:8]}"
        message["msg_id"] = msg_id
        message["source"] = self.node_name
        message["timestamp"] = time.time()

        self._gossip_seen.add(msg_id)

        # 1. Broadcast to connected WS clients
        await self._broadcast_ws(message)

        # 2. Push to known HTTP peers — build correct payload per message type
        if self.session:
            msg_type = message.get("type", "")
            if msg_type == "memory_update":
                # Bug #1: was sending message.get("entries", {}) which is empty;
                # a memory_update has "key" and "entry" (singular)
                key = message.get("key", "")
                entry = message.get("entry", {})
                payload = {"entries": {key: entry} if key else {}}
            elif msg_type == "trust_sign":
                payload = {"type": msg_type, "signer": message.get("signer", ""),
                           "target": message.get("target", "")}
            else:
                # Generic: send entries as-is
                payload = {"entries": message.get("entries", {})}

            for peer in self.peers:
                if peer.available and peer.circuit_breaker.can_execute():
                    try:
                        url = f'http://{peer.host}:{peer.port}/api/memory/push'
                        async with self.session.post(
                            url,
                            json=payload,
                            headers=self._auth_headers(path='/api/memory/push'),
                            timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                logger.debug(f"Gossip push to {peer.name}: OK")
                            else:
                                logger.debug(f"Gossip push to {peer.name}: {resp.status}")
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        logger.debug(f"Gossip push to {peer.name} failed: {e}")

    async def _gossip_propagate(self, message: Dict):
        """Propagate a gossip message (if not already seen)."""
        msg_id = message.get("msg_id", "")
        if not msg_id or msg_id in self._gossip_seen:
            return
        self._gossip_seen.add(msg_id)

        # Process locally based on type
        msg_type = message.get("type", "")
        if msg_type == "memory_update":
            key = message.get("key", "")
            entry = message.get("entry", {})
            if key and entry:
                self.memory.merge_from_sync({key: entry})
        elif msg_type == "trust_sign":
            signer = message.get("signer", "")
            target = message.get("target", "")
            if signer and target:
                self.web_of_trust.add_trust(signer, target)

        # Forward to other WS clients (with 1-hop limit to avoid storms)
        await self._broadcast_ws(message)

    # ========================================================================
    # BACKGROUND TASKS
    # ========================================================================

    async def sync_memory_to_peers(self):
        """Push local memory to all available peers (periodic HTTP sync)."""
        if not self.session:
            return
        memory_data = self.memory.get_all_for_sync()
        if not memory_data:
            return
        for peer in self.peers:
            if peer.available and peer.circuit_breaker.can_execute():
                try:
                    async with self.session.post(
                        f'http://{peer.host}:{peer.port}/api/memory/sync',
                        json={"entries": memory_data},
                        headers=self._auth_headers(path='/api/memory/sync'),
                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logger.debug(f"Synced {data.get('keys_merged', 0)} keys to {peer.name}")
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass

    async def auto_heal(self):
        """Check Ollama health and log alerts. Does NOT kill processes or restart services.
        
        CRIT-03 fix: Replaced fuser -k and systemctl restart with logging + alerting.
        Automatic process killing and service restarts are dangerous (RCE risk).
        Only log and alert; human intervention is required for restarts.
        """
        heal_interval = self.config.get("auto_heal_interval", 120)
        consecutive_failures = 0
        while self.heartbeat_running:
            await asyncio.sleep(heal_interval)
            try:
                async with self.session.get(
                    f'http://{self.ollama_host}:{self.ollama_port}/api/tags',
                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        consecutive_failures += 1
                        self.log_event("auto_heal", 
                            f"Ollama returned HTTP {resp.status} (failure #{consecutive_failures})", "warn")
                        logger.warning(
                            f"⚠️  Ollama health check failed (HTTP {resp.status}, "
                            f"failure #{consecutive_failures}). Manual intervention recommended."
                        )
                        # Broadcast alert via WS
                        await self._broadcast_ws({
                            'type': 'alert',
                            'alert': 'ollama_down',
                            'status_code': resp.status,
                            'consecutive_failures': consecutive_failures,
                            'message': f'Ollama health check failed (HTTP {resp.status})',
                            'node': self.node_name,
                            'timestamp': time.time()
                        })
                    else:
                        if consecutive_failures > 0:
                            self.log_event("auto_heal", f"Ollama recovered after {consecutive_failures} failures")
                            consecutive_failures = 0
            except (OSError, Exception) as e:
                consecutive_failures += 1
                self.log_event("auto_heal", f"Ollama unreachable: {e}", "error")
                logger.error(
                    f"🔴 Ollama is unreachable (failure #{consecutive_failures}): {e}. "
                    f"Manual restart may be needed: systemctl restart ollama"
                )
                await self._broadcast_ws({
                    'type': 'alert',
                    'alert': 'ollama_unreachable',
                    'error': str(e),
                    'consecutive_failures': consecutive_failures,
                    'message': f'Ollama is unreachable: {e}',
                    'node': self.node_name,
                    'timestamp': time.time()
                })

    async def _memory_sync_loop(self):
        """Bug #3 fix: Memory sync decoupled from auto_heal. Runs every 30s."""
        sync_interval = self.config.get("memory_sync_interval", 30)
        while self.heartbeat_running:
            await asyncio.sleep(sync_interval)
            await self.sync_memory_to_peers()

    async def _ws_memory_sync_loop(self):
        """Periodic memory sync via WS (lightweight delta push)."""
        while self.heartbeat_running:
            await asyncio.sleep(60)
            if self.ws_clients and self.memory.store:
                memory_data = self.memory.get_all_for_sync()
                if memory_data:
                    await self._broadcast_ws({
                        'type': 'memory_sync',
                        'entries': memory_data,
                        'vector_clock': self.memory.vector_clock.to_dict()
                    })

    # ========================================================================
    # FEATURE: OUTGOING WS CONNECTIONS TO PEERS (Bug #2 fix)
    # ========================================================================

    async def _connect_to_peers_ws(self):
        """Periodically establish outgoing WS connections to known peers.
        This enables real-time bidirectional sync between nodes."""
        while self.heartbeat_running:
            await asyncio.sleep(10)  # Initial delay then try every 30s
            if not self.session:
                continue
            for peer in self.peers:
                if not peer.available:
                    continue
                ws_key = f"ws_out:{peer.host}:{peer.port}"
                if ws_key in self.ws_clients:
                    continue  # Already connected
                try:
                    await self._connect_peer_ws(peer, ws_key)
                except Exception as e:
                    logger.debug(f"WS connect to {peer.name} failed: {e}")
            # Wait 30s between reconnect cycles
            await asyncio.sleep(30)

    async def _connect_peer_ws(self, peer: 'Peer', ws_key: str):
        """Connect to a single peer via WebSocket with HMAC auth. Keeps connection alive with pings."""
        ws_url = f'ws://{peer.host}:{peer.port}/ws'
        try:
            async with self.session.ws_connect(
                    ws_url,
                    heartbeat=15,  # Send ping every 15s to keep alive
                    timeout=aiohttp.ClientTimeout(total=10)) as ws:
                # Authenticate with HMAC
                ts = str(int(time.time()))
                import hmac as hmac_mod
                sig = hmac_mod.new(
                    self.p2p_secret.encode(),
                    f'/ws:{ts}'.encode(),
                    hashlib.sha256).hexdigest()
                await ws.send_json({'type': 'auth', 'hmac': sig, 'ts': ts})
                # Wait for auth_ack, ignoring any pre-auth broadcast messages
                auth_ok = False
                for _ in range(10):
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=5)
                    if msg.get('type') == 'auth_ack':
                        auth_ok = msg.get('status') == 'ok'
                        break
                    # Ignore pre-auth broadcasts (memory_update, memory_sync, etc.)
                    logger.debug(f"WS pre-auth message from {peer.name}: {msg.get('type', '?')}")
                if not auth_ok:
                    logger.warning(f"WS auth to {peer.name} failed: no auth_ack received")
                    await ws.close()
                    return

                logger.info(f"WS connected to {peer.name} ({peer.host}:{peer.port})")
                self.ws_clients[ws_key] = ws
                self.ws_authenticated.add(ws_key)

                # Request memory delta from peer
                await ws.send_json({
                    'type': 'memory_request',
                    'vector_clock': self.memory.vector_clock.to_dict()
                })

                # Listen for messages from this peer (persistent connection)
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                        except json.JSONDecodeError:
                            continue
                        await self._handle_incoming_ws_message(data, ws_key)
                    elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                        break
                    # PONG messages are handled automatically by the heartbeat

                logger.info(f"WS disconnected from {peer.name}, will reconnect")

        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionRefusedError) as e:
            logger.debug(f"WS connection to {peer.name} failed: {e}")
        finally:
            self.ws_clients.pop(ws_key, None)
            self.ws_authenticated.discard(ws_key)

    async def _handle_incoming_ws_message(self, data: Dict, source_id: str):
        """Handle a message received from an outgoing WS connection to a peer."""
        msg_type = data.get('type', '')

        if msg_type == 'memory_delta':
            entries = data.get('entries', {})
            if entries:
                merged = self.memory.merge_from_sync(entries)
                if merged > 0:
                    self.log_event("ws_sync", f"Merged {merged} entries from WS peer")
        elif msg_type == 'memory_full':
            entries = data.get('entries', {})
            if entries:
                merged = self.memory.merge_from_sync(entries)
                if merged > 0:
                    self.log_event("ws_sync", f"Merged {merged} entries from WS full sync")
        elif msg_type == 'memory_update':
            key = data.get('key', '')
            entry = data.get('entry', {})
            if key and entry:
                self.memory.merge_from_sync({key: entry})
        elif msg_type == 'memory_sync':
            entries = data.get('entries', {})
            if entries:
                merged = self.memory.merge_from_sync(entries)
                if merged > 0:
                    self.log_event("ws_sync", f"Merged {merged} entries from WS sync")
        elif msg_type == 'pong':
            pass  # heartbeat response
        elif msg_type == 'auth_ack':
            pass  # already authenticated
        elif msg_type == 'status':
            logger.debug(f"WS status from peer: {data.get('node', '?')}")
        elif msg_type == 'discover_ack':
            peer_info = data.get('peers', [])
            logger.debug(f"WS discover_ack: {len(peer_info)} peers")
        else:
            logger.debug(f"WS unknown message type: {msg_type}")

    async def _discovery_loop(self):
        """Periodic peer re-discovery."""
        interval = self.config.get("discovery_interval", 300)
        while self.heartbeat_running:
            await asyncio.sleep(interval)
            new_peers = await self.discovery.discover_all()
            for peer_info in new_peers:
                existing = [p for p in self.peers
                            if p.host == peer_info['host'] and p.port == peer_info.get('port', 8081)]
                if not existing:
                    peer = Peer(
                        name=peer_info.get('name', 'unknown'),
                        host=peer_info['host'],
                        port=peer_info.get('port', 8081),
                        models=peer_info.get('models', []),
                        public_key_hex=peer_info.get('public_key', '')
                    )
                    await self.add_peer(peer)
                    self.log_event("discovery", f"Auto-discovered {peer.name}")
            # Also check zero-config discovered peers
            zc_peers = self.zero_config.get_discovered_peers()
            for p in zc_peers:
                existing = [ep for ep in self.peers if ep.host == p['host'] and ep.port == p['port']]
                if not existing:
                    peer = Peer(
                        name=p['name'],
                        host=p['host'],
                        port=p['port'],
                        models=p.get('capabilities', {}).get('models', []),
                        public_key_hex=''
                    )
                    await self.add_peer(peer)
                    # Update peer capabilities
                    if 'capabilities' in p:
                        self.model_negotiator.update_peer_capabilities(p['name'], p['capabilities'])
                    self.log_event("zero_config", f"mDNS discovered {p['name']} at {p['host']}:{p['port']}")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    import sys
    import signal

    node_name = sys.argv[1] if len(sys.argv) > 1 else "bug"
    # Search for config: ~/.pinkybrain first, then relative to script
    home_config = Path.home() / ".pinkybrain" / "config" / f"{node_name}.json"
    script_config = Path(__file__).parent.parent / "config" / f"{node_name}.json"
    config_path = home_config if home_config.exists() else script_config
    config = load_config(str(config_path))
    if len(sys.argv) > 1:
        config["node_name"] = node_name

    brain = PinkyBrain(config)
    await brain.initialize()

    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("🛑 PinkyBrain shutting down...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    app = await brain.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    # LOW-03: TLS support via environment variables
    ssl_context = None
    cert_path = os.environ.get('PINKYBRAIN_CERT')
    key_path = os.environ.get('PINKYBRAIN_KEY')
    if cert_path and key_path:
        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(cert_path, key_path)
        logger.info(f"🔒 TLS enabled: {cert_path}")
    elif cert_path or key_path:
        logger.warning("⚠️  PINKYBRAIN_CERT or PINKYBRAIN_KEY missing — TLS not enabled")
    elif brain.host not in ('127.0.0.1', 'localhost', '::1'):
        logger.warning("⚠️  Running on public interface without TLS! Set PINKYBRAIN_CERT and PINKYBRAIN_KEY env vars.")

    site = web.TCPSite(runner, brain.host, brain.port, reuse_address=True, reuse_port=True,
                        ssl_context=ssl_context)
    await site.start()
    logger.info(f"🌐 PinkyBrain v{brain.version} on http://{brain.host}:{brain.port}")
    brain.log_event("server", f"Listening on {brain.host}:{brain.port}")

    if brain.stealth_mode:
        logger.info("🔒 Stealth mode ACTIVE — node is hidden from discovery")
    if brain.share_ai:
        logger.info("📤 AI sharing ENABLED — models available to the network")
    if not brain.share_ai:
        logger.info("🔇 AI sharing DISABLED — peers cannot use your models")
        logger.info("💡 Set share_ai: true to allow peers to use your CPU/RAM")

    tasks = [
        asyncio.create_task(brain.start_heartbeat()),
        asyncio.create_task(brain.auto_heal()),
        asyncio.create_task(brain._memory_sync_loop()),
    ]

    # P2P tasks
    tasks.extend([
        asyncio.create_task(brain._ws_memory_sync_loop()),
        asyncio.create_task(brain._connect_to_peers_ws()),
        asyncio.create_task(brain._discovery_loop()),
    ])

    # Start zero-config discovery
    await brain.zero_config.start()
    
    # Check for updates on startup
    update = await brain.auto_updater.check()
    if update:
        logger.info(f"🔄 Update available: v{update['latest']} (current v{update['current']})")
        brain.log_event("update", f"v{update['latest']} available")
    
    # Write PID for daemon mode
    brain.systray.write_pid(os.getpid())
    logger.info(f"🖥️ Daemon PID: {os.getpid()}")

    # Start resource guard monitor
    if brain.resource_guard:
        logger.info(f"🛡️ Resource Guard: {brain.resource_guard._state.value}")

    # Start tracker client announce loop
    if brain.tracker_client:
        asyncio.create_task(brain.tracker_client.announce_loop())
        asyncio.create_task(brain.tracker_client.discover_loop())
        logger.info(f"🌐 Tracker Client: announcing to mesh")

    await shutdown_event.wait()

    logger.info("Cleaning up...")
    brain.heartbeat_running = False
    # Stop resource guard
    if brain.resource_guard:
        await brain.resource_guard.stop()
    # Stop tracker client
    if brain.tracker_client:
        await brain.tracker_client.stop()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if brain.session:
        await brain.session.close()
    if brain.brain_llm:
        try:
            await brain.brain_llm.stop()
        except Exception:
            pass
    await runner.cleanup()
    logger.info("PinkyBrain stopped.")


if __name__ == '__main__':
    import sys
    node = sys.argv[1] if len(sys.argv) > 1 else "bug"
    logger.info(f"Starting PinkyBrain v5.2 as '{node}'")
    asyncio.run(main())