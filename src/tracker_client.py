#!/usr/bin/env python3
"""
🌐 PINKYBRAIN v5 — Tracker Client
===================================
Public mesh tracker client: announce, discover, and maintain a list of
public mesh nodes with contribution scores.

Security guarantees:
  - All communications over HTTPS/TLS (verified certs)
  - Ed25519-signed announcements (no private key material ever leaves the node)
  - Response validation: every tracker response is schema-validated
  - Rate limiting on announces (prevents tracker spam)
  - Exponential backoff on reconnection (prevents tracker flooding)
  - No private config/keys ever included in announcements
  - DoS protection: per-tracker request budget, malformed response rejection
"""

import asyncio
import aiohttp
import json
import time
import logging
import hashlib
import ssl
from typing import List, Dict, Any, Optional, Set
from collections import deque
from pathlib import Path

logger = logging.getLogger('PinkyBrain.TrackerClient')

# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_ANNOUNCE_INTERVAL = 300        # 5 minutes between announces
MIN_ANNOUNCE_INTERVAL = 60             # never announce more often than this
DISCOVER_CACHE_TTL = 120               # cache discover results for 2 min
MAX_BACKOFF = 3600                     # max backoff: 1 hour
BACKOFF_BASE = 2                       # exponential base
BACKOFF_INITIAL = 5                    # initial backoff: 5 seconds
MAX_TRACKERS = 5                        # max number of tracker URLs
MAX_NODES_PER_QUERY = 100              # cap results to prevent memory bomb
REQUEST_TIMEOUT = 15                    # seconds
ANNOUNCE_RATE_WINDOW = 60              # rate limit window (seconds)
ANNOUNCE_RATE_MAX = 3                  # max announces per window
MAX_RESPONSE_SIZE = 1 * 1024 * 1024    # 1 MB max response size

# Valid fields in an announcement (whitelist — anything else is stripped)
VALID_ANNOUNCE_FIELDS = {
    'node_id', 'capabilities', 'uptime_seconds', 'address',
    'models', 'signature', 'timestamp', 'name'
}

VALID_CAPABILITY_FIELDS = {
    'cpu_cores', 'ram_total_mb', 'ram_share_mb', 'gpu',
    'models', 'bandwidth_kbps', 'max_model_category'
}


# ============================================================================
# SCHEMA VALIDATION
# ============================================================================

class TrackerResponseValidator:
    """Validate all responses from trackers. Never trust blindly."""

    @staticmethod
    def validate_announce_response(data: Any) -> bool:
        """Validate response to an announce request."""
        if not isinstance(data, dict):
            return False
        # Must have status field
        if 'status' not in data:
            return False
        # Status should be 'ok' or 'accepted'
        if data['status'] not in ('ok', 'accepted', 'acknowledged'):
            return False
        return True

    @staticmethod
    def validate_discover_response(data: Any) -> bool:
        """Validate response to a discover request. Returns list of nodes."""
        if not isinstance(data, dict):
            return False
        nodes = data.get('nodes', data.get('results', []))
        if not isinstance(nodes, list):
            return False
        # Cap results
        if len(nodes) > MAX_NODES_PER_QUERY:
            logger.warning(f"Tracker returned {len(nodes)} nodes, capping to {MAX_NODES_PER_QUERY}")
            nodes = nodes[:MAX_NODES_PER_QUERY]
        # Validate each node entry
        valid_nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if 'node_id' not in node and 'address' not in node:
                continue  # skip malformed entries
            valid_nodes.append(node)
        data['_validated_nodes'] = valid_nodes
        return True

    @staticmethod
    def validate_score_response(data: Any) -> bool:
        """Validate response to a score query."""
        if not isinstance(data, dict):
            return False
        if 'score' not in data:
            return False
        score = data['score']
        if not isinstance(score, (int, float)) or score < 0 or score > 1000:
            return False
        return True

    @staticmethod
    def sanitize_announcement(announcement: Dict) -> Dict:
        """Strip any field that shouldn't be sent to the tracker.
        Prevents leaking private keys, config secrets, etc."""
        sanitized = {}
        for key in VALID_ANNOUNCE_FIELDS:
            if key in announcement:
                sanitized[key] = announcement[key]

        # Deep-sanitize capabilities
        if 'capabilities' in sanitized and isinstance(sanitized['capabilities'], dict):
            clean_caps = {}
            for key in VALID_CAPABILITY_FIELDS:
                if key in sanitized['capabilities']:
                    clean_caps[key] = sanitized['capabilities'][key]
            sanitized['capabilities'] = clean_caps

        # Never allow these fields (safety net)
        for forbidden in ('private_key', 'secret', 'p2p_secret', 'password',
                          'api_key', 'token', 'auth', 'config'):
            sanitized.pop(forbidden, None)
            if 'capabilities' in sanitized and isinstance(sanitized['capabilities'], dict):
                sanitized['capabilities'].pop(forbidden, None)

        return sanitized


# ============================================================================
# KNOWN NODE — a discovered public mesh node
# ============================================================================

class KnownNode:
    """A node discovered via the public tracker."""

    def __init__(self, node_id: str, address: str, capabilities: Dict = None,
                 score: float = 0.0, first_seen: float = None, name: str = ""):
        self.node_id = node_id
        self.address = address
        self.name = name
        self.capabilities = capabilities or {}
        self.score = score
        self.first_seen = first_seen or time.time()
        self.last_seen = time.time()
        self.uptime_seconds = 0
        self.models: List[str] = capabilities.get('models', []) if capabilities else []
        self.announce_failures = 0
        self.verified = False  # Whether we've verified their Ed25519 identity

    def update(self, data: Dict):
        """Update node info from tracker response."""
        if 'capabilities' in data:
            self.capabilities = data['capabilities']
            self.models = data['capabilities'].get('models', [])
        if 'score' in data:
            self.score = data['score']
        if 'uptime_seconds' in data:
            self.uptime_seconds = data['uptime_seconds']
        if 'name' in data:
            self.name = data['name']
        self.last_seen = time.time()

    @property
    def is_stale(self) -> bool:
        """Node is stale if not seen for >15 minutes."""
        return time.time() - self.last_seen > 900

    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id,
            'address': self.address,
            'name': self.name,
            'capabilities': self.capabilities,
            'score': round(self.score, 2),
            'first_seen': round(self.first_seen, 1),
            'last_seen': round(self.last_seen, 1),
            'uptime_seconds': self.uptime_seconds,
            'models': self.models,
            'verified': self.verified
        }


# ============================================================================
# TRACKER STATE — per-tracker connection state
# ============================================================================

class TrackerState:
    """State for a single tracker connection."""

    def __init__(self, url: str):
        self.url = url.rstrip('/')
        self.connected = False
        self.last_announce = 0
        self.last_discover = 0
        self.announce_count = 0
        self.failure_count = 0
        self.last_failure = 0
        self.backoff_until = 0
        self.backoff_level = 0
        # Rate limit tracking
        self._announce_timestamps: deque = deque(maxlen=ANNOUNCE_RATE_MAX + 2)

    @property
    def is_backing_off(self) -> bool:
        return time.time() < self.backoff_until

    @property
    def backoff_remaining(self) -> float:
        return max(0, self.backoff_until - time.time())

    def record_success(self):
        """Reset backoff on successful communication."""
        self.connected = True
        self.failure_count = 0
        self.backoff_level = 0
        self.backoff_until = 0

    def record_failure(self):
        """Increment backoff on failure."""
        self.failure_count += 1
        self.last_failure = time.time()
        self.backoff_level = min(self.backoff_level + 1, 10)
        delay = min(BACKOFF_INITIAL * (BACKOFF_BASE ** self.backoff_level), MAX_BACKOFF)
        # Add jitter: ±25%
        jitter = delay * 0.25 * (hashlib.sha256(f"{self.url}:{time.time()}".encode()).hexdigest()[0] == '0' and 1 or -1)
        self.backoff_until = time.time() + delay + jitter
        logger.info(f"Tracker {self.url} failure #{self.failure_count}, "
                    f"backoff {delay:.0f}s (level {self.backoff_level})")

    def can_announce(self) -> bool:
        """Check rate limit for announces."""
        if self.is_backing_off:
            return False
        now = time.time()
        # Prune old timestamps
        while self._announce_timestamps and now - self._announce_timestamps[0] > ANNOUNCE_RATE_WINDOW:
            self._announce_timestamps.popleft()
        if len(self._announce_timestamps) >= ANNOUNCE_RATE_MAX:
            return False
        return True

    def record_announce(self):
        """Record that we just announced."""
        self._announce_timestamps.append(time.time())
        self.last_announce = time.time()
        self.announce_count += 1


# ============================================================================
# TRACKER CLIENT — main module
# ============================================================================

class TrackerClient:
    """Public mesh tracker client.

    Handles:
      1. Announcing this node to one or more trackers
      2. Discovering nodes that match queries (model, RAM, GPU, etc.)
      3. Maintaining a local list of known public mesh nodes with scores
      4. Automatic reconnection with exponential backoff
      5. Multi-tracker fallback

    Security:
      - All HTTP calls use TLS (https://) with cert verification
      - Announcements are Ed25519-signed, no private keys sent
      - Tracker responses are validated before processing
      - Rate limiting prevents tracker flooding
      - Announcements are sanitized (no private data leaks)
    """

    def __init__(self, identity, config: Dict = None):
        """
        Args:
            identity: NodeIdentity instance (from pinkybrain_v5) — provides Ed25519 signing
            config: dict with public_mesh configuration
        """
        self.identity = identity
        config = config or {}

        # Tracker URLs
        tracker_urls = config.get('tracker_url', [])
        if isinstance(tracker_urls, str):
            tracker_urls = [tracker_urls]
        self.trackers: List[TrackerState] = []
        for url in tracker_urls[:MAX_TRACKERS]:
            # Enforce HTTPS
            if not url.startswith('https://'):
                logger.warning(f"Tracker URL must be HTTPS, skipping: {url}")
                continue
            self.trackers.append(TrackerState(url))

        if not self.trackers:
            logger.info("No HTTPS tracker URLs configured, tracker client will be idle")

        # Node's own sharing config
        self.enabled = config.get('enabled', False)
        self.max_ram_share_mb = config.get('max_ram_share_mb', 0)
        self.max_cpu_percent = config.get('max_cpu_percent', 0)
        self.gpu_share = config.get('gpu_share', False)
        self.models_share: List[str] = config.get('models_share', [])
        self.bandwidth_limit_kbps = config.get('bandwidth_limit_kbps', 0)
        self.priority = config.get('priority', 'local_first')

        # Known nodes from the mesh
        self.known_nodes: Dict[str, KnownNode] = {}  # node_id -> KnownNode

        # Announcement interval
        self.announce_interval = max(
            config.get('announce_interval', DEFAULT_ANNOUNCE_INTERVAL),
            MIN_ANNOUNCE_INTERVAL
        )

        # Discover cache
        self._discover_cache: Dict[str, tuple] = {}  # query_key -> (timestamp, [nodes])
        self._discover_cache_ttl = config.get('discover_cache_ttl', DISCOVER_CACHE_TTL)

        # HTTP session (created on start)
        self._session: Optional[aiohttp.ClientSession] = None

        # Background tasks
        self._running = False
        self._announce_task: Optional[asyncio.Task] = None
        self._refresh_task: Optional[asyncio.Task] = None

        # Uptime tracking
        self._start_time = time.time()

        # TLS context — verify certs, no fallback
        self._ssl_context = ssl.create_default_context()
        # Do NOT disable cert verification
        # self._ssl_context.check_hostname = True  (default)
        # self._ssl_context.verify_mode = ssl.CERT_REQUIRED  (default)

        # Validator
        self.validator = TrackerResponseValidator()

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    async def start(self):
        """Start the tracker client background tasks."""
        if not self.enabled:
            logger.info("Public mesh disabled, tracker client not starting")
            return
        if not self.trackers:
            logger.warning("No trackers configured, tracker client idle")
            return

        self._running = True
        self._start_time = time.time()

        # Create HTTP session with TLS
        connector = aiohttp.TCPConnector(ssl=self._ssl_context, limit=20)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)

        # Initial announce
        await self.announce()

        # Start background announce loop
        self._announce_task = asyncio.create_task(self._announce_loop())
        # Start stale node cleanup
        self._refresh_task = asyncio.create_task(self._refresh_loop())

        logger.info(f"Tracker client started: {len(self.trackers)} tracker(s), "
                    f"announce every {self.announce_interval}s")

    async def stop(self):
        """Stop the tracker client."""
        self._running = False
        if self._announce_task:
            self._announce_task.cancel()
            try:
                await self._announce_task
            except asyncio.CancelledError:
                pass
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("Tracker client stopped")

    # ========================================================================
    # ANNOUNCE
    # ========================================================================

    def _build_announcement(self) -> Dict:
        """Build the announcement payload for this node.
        Only includes whitelisted fields. Signs with Ed25519.
        No private keys, secrets, or config ever included."""
        uptime = int(time.time() - self._start_time)
        timestamp = int(time.time())

        announcement = {
            'node_id': self.identity.public_key_hex,
            'name': self.identity.name,
            'capabilities': {
                'ram_share_mb': self.max_ram_share_mb,
                'cpu_cores': 0,  # will be filled by caller if desired
                'gpu': self.gpu_share,
                'models': self.models_share,
                'bandwidth_kbps': self.bandwidth_limit_kbps,
            },
            'uptime_seconds': uptime,
            'address': '',  # filled by caller
            'timestamp': timestamp,
        }

        # Sign the announcement
        canonical = json.dumps(announcement, sort_keys=True, separators=(',', ':'))
        signature = self.identity.sign(canonical)
        announcement['signature'] = signature

        # Sanitize: strip any forbidden fields
        announcement = self.validator.sanitize_announcement(announcement)

        return announcement

    async def announce(self, address: str = None) -> bool:
        """Announce this node to all trackers.
        Args:
            address: Optional override for this node's address (host:port)
        Returns:
            True if at least one tracker accepted the announcement
        """
        if not self._session or not self.trackers:
            return False

        announcement = self._build_announcement()
        if address:
            announcement['address'] = address

        success = False
        for tracker in self.trackers:
            if not tracker.can_announce():
                if tracker.is_backing_off:
                    logger.debug(f"Tracker {tracker.url} in backoff ({tracker.backoff_remaining:.0f}s)")
                continue

            try:
                result = await self._post_to_tracker(tracker, '/api/announce', announcement)
                if result is not None and self.validator.validate_announce_response(result):
                    tracker.record_success()
                    tracker.record_announce()
                    success = True
                    logger.debug(f"Announced to {tracker.url}")
                else:
                    tracker.record_failure()
                    logger.warning(f"Invalid announce response from {tracker.url}")
            except Exception as e:
                tracker.record_failure()
                logger.warning(f"Announce failed for {tracker.url}: {e}")

        return success

    # ========================================================================
    # DISCOVER
    # ========================================================================

    async def discover(self, model: str = None, min_ram_mb: int = 0,
                       gpu_required: bool = False,
                       max_results: int = 20) -> List[KnownNode]:
        """Discover nodes matching criteria.
        Queries all trackers with fallback. Results are cached briefly.
        Args:
            model: Model name to search for
            min_ram_mb: Minimum RAM share in MB
            gpu_required: Whether GPU is required
            max_results: Maximum number of results
        Returns:
            List of KnownNode objects matching criteria
        """
        if not self._session or not self.trackers:
            return self._local_discover(model, min_ram_mb, gpu_required, max_results)

        # Build cache key
        cache_key = f"{model}:{min_ram_mb}:{gpu_required}"
        cached = self._discover_cache.get(cache_key)
        if cached and time.time() - cached[0] < self._discover_cache_ttl:
            nodes = cached[1][:max_results]
            return nodes

        # Build query params
        params = {}
        if model:
            params['model'] = model
        if min_ram_mb:
            params['min_ram'] = min_ram_mb
        if gpu_required:
            params['gpu'] = 'true'

        # Try each tracker
        raw_nodes = None
        for tracker in self.trackers:
            if tracker.is_backing_off:
                continue
            try:
                result = await self._get_from_tracker(tracker, '/api/find', params)
                if result is not None and self.validator.validate_discover_response(result):
                    raw_nodes = result.get('_validated_nodes', [])
                    tracker.record_success()
                    tracker.last_discover = time.time()
                    break  # got results from this tracker
                else:
                    tracker.record_failure()
            except Exception as e:
                tracker.record_failure()
                logger.debug(f"Discover failed for {tracker.url}: {e}")

        if raw_nodes is None:
            # All trackers failed — fall back to local known nodes
            return self._local_discover(model, min_ram_mb, gpu_required, max_results)

        # Update known nodes from tracker response
        for node_data in raw_nodes:
            self._update_known_node(node_data)

        # Filter and return
        results = self._local_discover(model, min_ram_mb, gpu_required, max_results)
        self._discover_cache[cache_key] = (time.time(), results)

        return results

    def _local_discover(self, model: str = None, min_ram_mb: int = 0,
                        gpu_required: bool = False, max_results: int = 20) -> List[KnownNode]:
        """Search local known_nodes cache for matching nodes."""
        matches = []
        for node in self.known_nodes.values():
            if node.is_stale:
                continue
            # Model filter
            if model and model not in node.models:
                continue
            # RAM filter
            if min_ram_mb:
                node_ram = node.capabilities.get('ram_share_mb', 0)
                if node_ram < min_ram_mb:
                    continue
            # GPU filter
            if gpu_required and not node.capabilities.get('gpu', False):
                continue
            matches.append(node)

        # Sort by score (descending) then by last_seen (most recent first)
        matches.sort(key=lambda n: (-n.score, -n.last_seen))
        return matches[:max_results]

    def _update_known_node(self, data: Dict):
        """Update or create a KnownNode from tracker data."""
        node_id = data.get('node_id', '')
        address = data.get('address', '')
        if not node_id and not address:
            return

        # Use address as fallback key if no node_id
        key = node_id or address

        if key in self.known_nodes:
            self.known_nodes[key].update(data)
        else:
            node = KnownNode(
                node_id=key,
                address=address,
                capabilities=data.get('capabilities', {}),
                score=data.get('score', 0.0),
                name=data.get('name', '')
            )
            self.known_nodes[key] = node

    # ========================================================================
    # SCORES
    # ========================================================================

    async def get_node_score(self, node_id: str) -> Optional[float]:
        """Query trackers for a specific node's contribution score."""
        if not self._session or not self.trackers:
            # Fall back to local data
            node = self.known_nodes.get(node_id)
            return node.score if node else None

        for tracker in self.trackers:
            if tracker.is_backing_off:
                continue
            try:
                result = await self._get_from_tracker(
                    tracker, f'/api/score/{node_id}', {})
                if result and self.validator.validate_score_response(result):
                    tracker.record_success()
                    score = result['score']
                    # Update local cache
                    if node_id in self.known_nodes:
                        self.known_nodes[node_id].score = score
                    return score
                else:
                    tracker.record_failure()
            except Exception as e:
                tracker.record_failure()
                logger.debug(f"Score query failed for {tracker.url}: {e}")

        # Fall back to local
        node = self.known_nodes.get(node_id)
        return node.score if node else None

    # ========================================================================
    # HTTP HELPERS (TLS-only, validated)
    # ========================================================================

    async def _post_to_tracker(self, tracker: TrackerState, path: str,
                                payload: Dict) -> Optional[Dict]:
        """POST to a tracker. Validates TLS. Returns parsed JSON or None."""
        url = f"{tracker.url}{path}"
        try:
            # Sign the request
            ts = str(int(time.time()))
            challenge = f"{self.identity.name}:{ts}"
            sig = self.identity.sign(challenge)

            headers = {
                'Content-Type': 'application/json',
                'X-PinkyBrain-Node': self.identity.name,
                'X-PinkyBrain-Key': self.identity.public_key_hex,
                'X-PinkyBrain-TS': ts,
                'X-PinkyBrain-Sig': sig,
            }

            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                if resp.status == 429:
                    logger.warning(f"Tracker {tracker.url} rate-limited us")
                    tracker.record_failure()
                    return None
                if resp.status >= 500:
                    logger.warning(f"Tracker {tracker.url} server error: {resp.status}")
                    tracker.record_failure()
                    return None
                if resp.status >= 400:
                    logger.debug(f"Tracker {tracker.url} client error: {resp.status}")
                    return None
                if resp.status != 200:
                    logger.debug(f"Tracker {tracker.url} unexpected status: {resp.status}")
                    return None

                # Check content length
                content_length = resp.content_length
                if content_length and content_length > MAX_RESPONSE_SIZE:
                    logger.warning(f"Tracker {tracker.url} response too large: {content_length}")
                    return None

                data = await resp.json(content_type=None)
                return data

        except aiohttp.ClientSSLError as e:
            logger.error(f"TLS error with tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None
        except aiohttp.ClientConnectorError as e:
            logger.debug(f"Connection error with tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None
        except aiohttp.ClientError as e:
            logger.debug(f"HTTP error with tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None
        except asyncio.TimeoutError:
            logger.debug(f"Timeout with tracker {tracker.url}")
            tracker.record_failure()
            return None
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid JSON from tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None

    async def _get_from_tracker(self, tracker: TrackerState, path: str,
                                 params: Dict) -> Optional[Dict]:
        """GET from a tracker. Validates TLS. Returns parsed JSON or None."""
        url = f"{tracker.url}{path}"
        try:
            ts = str(int(time.time()))
            challenge = f"{self.identity.name}:{ts}"
            sig = self.identity.sign(challenge)

            headers = {
                'X-PinkyBrain-Node': self.identity.name,
                'X-PinkyBrain-Key': self.identity.public_key_hex,
                'X-PinkyBrain-TS': ts,
                'X-PinkyBrain-Sig': sig,
            }

            async with self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                if resp.status == 429:
                    logger.warning(f"Tracker {tracker.url} rate-limited us")
                    tracker.record_failure()
                    return None
                if resp.status >= 500:
                    tracker.record_failure()
                    return None
                if resp.status != 200:
                    return None

                content_length = resp.content_length
                if content_length and content_length > MAX_RESPONSE_SIZE:
                    logger.warning(f"Tracker {tracker.url} response too large: {content_length}")
                    return None

                data = await resp.json(content_type=None)
                return data

        except aiohttp.ClientSSLError as e:
            logger.error(f"TLS error with tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None
        except aiohttp.ClientConnectorError as e:
            logger.debug(f"Connection error with tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None
        except aiohttp.ClientError as e:
            logger.debug(f"HTTP error with tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None
        except asyncio.TimeoutError:
            tracker.record_failure()
            return None
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid JSON from tracker {tracker.url}: {e}")
            tracker.record_failure()
            return None

    # ========================================================================
    # BACKGROUND LOOPS
    # ========================================================================

    async def _announce_loop(self):
        """Periodically re-announce to trackers."""
        while self._running:
            await asyncio.sleep(self.announce_interval)
            if self._running:
                await self.announce()

    async def _refresh_loop(self):
        """Periodically clean up stale nodes and refresh scores."""
        while self._running:
            await asyncio.sleep(120)  # every 2 min
            if not self._running:
                break
            # Remove stale nodes
            stale = [nid for nid, node in self.known_nodes.items() if node.is_stale]
            for nid in stale:
                del self.known_nodes[nid]
            if stale:
                logger.debug(f"Removed {len(stale)} stale nodes")

            # Clear expired cache entries
            now = time.time()
            expired_keys = [k for k, (ts, _) in self._discover_cache.items()
                           if now - ts > self._discover_cache_ttl]
            for k in expired_keys:
                del self._discover_cache[k]

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def get_known_nodes(self) -> List[Dict]:
        """Get all known nodes as dicts."""
        return [n.to_dict() for n in self.known_nodes.values() if not n.is_stale]

    def get_tracker_status(self) -> List[Dict]:
        """Get status of all tracker connections."""
        result = []
        for t in self.trackers:
            result.append({
                'url': t.url,
                'connected': t.connected,
                'backing_off': t.is_backing_off,
                'backoff_remaining': round(t.backoff_remaining, 1),
                'failure_count': t.failure_count,
                'announce_count': t.announce_count,
                'last_announce': round(t.last_announce, 1),
                'last_discover': round(t.last_discover, 1),
            })
        return result

    def update_own_config(self, address: str = None, cpu_cores: int = 0,
                          ram_total_mb: int = 0, max_model_category: str = ''):
        """Update the node's own capabilities for the next announcement.
        Called by the main PinkyBrain class after detecting hardware."""
        # Store extra info that gets included in next announcement
        self._own_address = address or getattr(self, '_own_address', '')
        self._own_cpu_cores = cpu_cores
        self._own_ram_total_mb = ram_total_mb
        self._own_max_model_category = max_model_category

    def _build_announcement(self) -> Dict:
        """Build the announcement payload. Overrides parent to include auto-detected info."""
        uptime = int(time.time() - self._start_time)
        timestamp = int(time.time())

        caps = {
            'ram_share_mb': self.max_ram_share_mb,
            'cpu_cores': getattr(self, '_own_cpu_cores', 0),
            'ram_total_mb': getattr(self, '_own_ram_total_mb', 0),
            'gpu': self.gpu_share,
            'models': self.models_share,
            'bandwidth_kbps': self.bandwidth_limit_kbps,
            'max_model_category': getattr(self, '_own_max_model_category', ''),
        }

        announcement = {
            'node_id': self.identity.public_key_hex,
            'name': self.identity.name,
            'capabilities': caps,
            'uptime_seconds': uptime,
            'address': getattr(self, '_own_address', ''),
            'timestamp': timestamp,
        }

        # Sign the announcement
        canonical = json.dumps(announcement, sort_keys=True, separators=(',', ':'))
        signature = self.identity.sign(canonical)
        announcement['signature'] = signature

        # Sanitize: strip any forbidden fields
        announcement = self.validator.sanitize_announcement(announcement)

        return announcement

    def to_dict(self) -> Dict:
        """Serialize tracker client state."""
        return {
            'enabled': self.enabled,
            'trackers': self.get_tracker_status(),
            'known_nodes_count': len(self.known_nodes),
            'announce_interval': self.announce_interval,
            'models_shared': self.models_share,
            'max_ram_share_mb': self.max_ram_share_mb,
            'max_cpu_percent': self.max_cpu_percent,
            'gpu_share': self.gpu_share,
        }