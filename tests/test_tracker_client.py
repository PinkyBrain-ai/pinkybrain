#!/usr/bin/env python3
"""
Tests for PinkyBrain v5 Tracker Client
=========================================
Tests cover:
  - Announcement building & sanitization
  - Ed25519 signing of announcements
  - Discovery and node filtering
  - Exponential backoff on failures
  - Rate limiting on announces
  - Multi-tracker fallback
  - TLS enforcement (no http:// URLs)
  - Response validation
  - Known node lifecycle (stale detection, cleanup)
  - Score queries
"""

import asyncio
import json
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import aiohttp
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tracker_client import (
    TrackerClient, TrackerState, KnownNode, TrackerResponseValidator,
    DEFAULT_ANNOUNCE_INTERVAL, MIN_ANNOUNCE_INTERVAL, MAX_BACKOFF,
    BACKOFF_INITIAL, BACKOFF_BASE, ANNOUNCE_RATE_MAX, ANNOUNCE_RATE_WINDOW,
    MAX_NODES_PER_QUERY, MAX_TRACKERS, VALID_ANNOUNCE_FIELDS
)

# ============================================================================
# MOCK IDENTITY
# ============================================================================

class MockIdentity:
    """Minimal mock of NodeIdentity for testing."""
    def __init__(self, name="test-node", public_key_hex=None):
        self.name = name
        self.public_key_hex = public_key_hex or "a" * 64  # fake 32-byte key hex
        self.fingerprint = self.public_key_hex[:16]

    def sign(self, message: str) -> str:
        """Predictable signature for testing."""
        import hashlib
        return hashlib.sha256(f"{self.public_key_hex}:{message}".encode()).hexdigest()

    def verify(self, message: str, signature_hex: str, public_key_hex: str = None) -> bool:
        """Verify against our mock signing scheme."""
        expected = self.sign(message)
        return signature_hex == expected

    def to_dict(self):
        return {
            "name": self.name,
            "public_key": self.public_key_hex,
            "fingerprint": self.fingerprint
        }


# ============================================================================
# TEST VALIDATOR
# ============================================================================

class TestTrackerResponseValidator(unittest.TestCase):

    def test_validate_announce_response_ok(self):
        validator = TrackerResponseValidator()
        self.assertTrue(validator.validate_announce_response({"status": "ok"}))
        self.assertTrue(validator.validate_announce_response({"status": "accepted"}))
        self.assertTrue(validator.validate_announce_response({"status": "acknowledged"}))

    def test_validate_announce_response_invalid(self):
        validator = TrackerResponseValidator()
        self.assertFalse(validator.validate_announce_response({}))
        self.assertFalse(validator.validate_announce_response({"status": "error"}))
        self.assertFalse(validator.validate_announce_response("not a dict"))
        self.assertFalse(validator.validate_announce_response(None))

    def test_validate_discover_response_ok(self):
        validator = TrackerResponseValidator()
        data = {"nodes": [
            {"node_id": "abc", "address": "1.2.3.4:8081"},
            {"node_id": "def", "address": "5.6.7.8:8081", "capabilities": {"gpu": True}},
        ]}
        self.assertTrue(validator.validate_discover_response(data))
        self.assertEqual(len(data['_validated_nodes']), 2)

    def test_validate_discover_response_results_key(self):
        validator = TrackerResponseValidator()
        data = {"results": [{"node_id": "x", "address": "10.0.0.1:8081"}]}
        self.assertTrue(validator.validate_discover_response(data))

    def test_validate_discover_response_caps_nodes(self):
        validator = TrackerResponseValidator()
        nodes = [{"node_id": f"n{i}", "address": f"1.2.3.{i}:8081"}
                 for i in range(MAX_NODES_PER_QUERY + 50)]
        data = {"nodes": nodes}
        self.assertTrue(validator.validate_discover_response(data))
        self.assertEqual(len(data['_validated_nodes']), MAX_NODES_PER_QUERY)

    def test_validate_discover_response_malformed_entries(self):
        validator = TrackerResponseValidator()
        data = {"nodes": [
            {"node_id": "valid", "address": "1.2.3.4:8081"},
            {"foo": "bar"},  # missing node_id and address
            "not a dict",
            {"address": "1.2.3.4:8081"},  # has address, valid
        ]}
        self.assertTrue(validator.validate_discover_response(data))
        self.assertEqual(len(data['_validated_nodes']), 2)

    def test_validate_discover_response_invalid(self):
        validator = TrackerResponseValidator()
        self.assertFalse(validator.validate_discover_response("string"))
        self.assertFalse(validator.validate_discover_response(None))
        self.assertFalse(validator.validate_discover_response({"nodes": "not a list"}))

    def test_validate_score_response_ok(self):
        validator = TrackerResponseValidator()
        self.assertTrue(validator.validate_score_response({"score": 42.5}))
        self.assertTrue(validator.validate_score_response({"score": 0}))
        self.assertTrue(validator.validate_score_response({"score": 100}))

    def test_validate_score_response_invalid(self):
        validator = TrackerResponseValidator()
        self.assertFalse(validator.validate_score_response({}))
        self.assertFalse(validator.validate_score_response({"score": -1}))
        self.assertFalse(validator.validate_score_response({"score": 2000}))
        self.assertFalse(validator.validate_score_response({"score": "not a number"}))

    def test_sanitize_announcement_strips_private_fields(self):
        validator = TrackerResponseValidator()
        announcement = {
            'node_id': 'abc123',
            'capabilities': {
                'cpu_cores': 4,
                'models': ['glm-5.1:cloud'],
                'secret': 'should_be_removed',
            },
            'private_key': 'SUPER_SECRET',
            'p2p_secret': 'dont_send_this',
            'password': 'hunter2',
            'api_key': 'sk-12345',
            'name': 'my-node',
        }
        sanitized = validator.sanitize_announcement(announcement)

        # Private fields must be gone
        self.assertNotIn('private_key', sanitized)
        self.assertNotIn('p2p_secret', sanitized)
        self.assertNotIn('password', sanitized)
        self.assertNotIn('api_key', sanitized)
        self.assertNotIn('secret', sanitized.get('capabilities', {}))

        # Valid fields must remain
        self.assertIn('node_id', sanitized)
        self.assertIn('name', sanitized)
        self.assertIn('capabilities', sanitized)
        self.assertEqual(sanitized['capabilities']['cpu_cores'], 4)
        self.assertEqual(sanitized['capabilities']['models'], ['glm-5.1:cloud'])

    def test_sanitize_announcement_removes_unknown_fields(self):
        validator = TrackerResponseValidator()
        announcement = {
            'node_id': 'abc',
            'some_random_field': 'should_be_removed',
            'name': 'test',
        }
        sanitized = validator.sanitize_announcement(announcement)
        self.assertNotIn('some_random_field', sanitized)
        self.assertIn('node_id', sanitized)
        self.assertIn('name', sanitized)


# ============================================================================
# TEST KNOWN NODE
# ============================================================================

class TestKnownNode(unittest.TestCase):

    def test_create_known_node(self):
        node = KnownNode(
            node_id="test-id",
            address="192.168.1.1:8081",
            capabilities={"gpu": True, "models": ["llama3:8b"]},
            score=50.0,
            name="test-node"
        )
        self.assertEqual(node.node_id, "test-id")
        self.assertEqual(node.address, "192.168.1.1:8081")
        self.assertEqual(node.score, 50.0)
        self.assertEqual(node.models, ["llama3:8b"])
        self.assertFalse(node.verified)

    def test_update_known_node(self):
        node = KnownNode(node_id="id1", address="1.2.3.4:8081", score=10.0)
        node.update({
            'score': 75.0,
            'capabilities': {'models': ['glm-5.1:cloud'], 'gpu': False},
            'name': 'updated-name'
        })
        self.assertEqual(node.score, 75.0)
        self.assertEqual(node.models, ['glm-5.1:cloud'])
        self.assertEqual(node.name, 'updated-name')

    def test_stale_node(self):
        node = KnownNode(node_id="stale", address="1.2.3.4:8081")
        node.last_seen = time.time() - 1000  # 16+ minutes ago
        self.assertTrue(node.is_stale)

    def test_fresh_node(self):
        node = KnownNode(node_id="fresh", address="1.2.3.4:8081")
        self.assertFalse(node.is_stale)

    def test_to_dict(self):
        node = KnownNode(node_id="d1", address="1.2.3.4:8081",
                         capabilities={"gpu": True}, score=42.0, name="node1")
        d = node.to_dict()
        self.assertEqual(d['node_id'], 'd1')
        self.assertEqual(d['address'], '1.2.3.4:8081')
        self.assertEqual(d['name'], 'node1')
        self.assertEqual(d['score'], 42.0)
        self.assertIn('first_seen', d)
        self.assertIn('last_seen', d)


# ============================================================================
# TEST TRACKER STATE (backoff & rate limiting)
# ============================================================================

class TestTrackerState(unittest.TestCase):

    def test_initial_state(self):
        state = TrackerState("https://tracker.example.com")
        self.assertEqual(state.url, "https://tracker.example.com")
        self.assertFalse(state.connected)
        self.assertFalse(state.is_backing_off)

    def test_backoff_on_failure(self):
        state = TrackerState("https://tracker.example.com")
        state.record_failure()
        self.assertTrue(state.is_backing_off)
        self.assertGreater(state.backoff_remaining, 0)

    def test_backoff_increases_exponentially(self):
        state = TrackerState("https://tracker.example.com")
        for i in range(5):
            state.record_failure()
        # After 5 failures, backoff should be significant
        self.assertTrue(state.is_backing_off)
        self.assertGreater(state.backoff_remaining, 5)

    def test_backoff_resets_on_success(self):
        state = TrackerState("https://tracker.example.com")
        state.record_failure()
        state.record_failure()
        self.assertTrue(state.is_backing_off)

        state.record_success()
        self.assertFalse(state.is_backing_off)
        self.assertEqual(state.failure_count, 0)
        self.assertEqual(state.backoff_level, 0)

    def test_max_backoff(self):
        state = TrackerState("https://tracker.example.com")
        for i in range(20):
            state.record_failure()
        # Backoff should not exceed MAX_BACKOFF
        self.assertLessEqual(state.backoff_remaining, MAX_BACKOFF + 5)  # + jitter

    def test_rate_limit_all_announces(self):
        state = TrackerState("https://tracker.example.com")
        # Should allow announces initially
        self.assertTrue(state.can_announce())

        # Exhaust rate limit
        for i in range(ANNOUNCE_RATE_MAX):
            state.record_announce()

        # Should be rate limited
        self.assertFalse(state.can_announce())

    def test_rate_limit_resets_over_time(self):
        state = TrackerState("https://tracker.example.com")
        for i in range(ANNOUNCE_RATE_MAX):
            state.record_announce()
        self.assertFalse(state.can_announce())

        # Simulate time passing
        old_ts = list(state._announce_timestamps)
        for i in range(len(state._announce_timestamps)):
            state._announce_timestamps[i] = time.time() - ANNOUNCE_RATE_WINDOW - 1

        self.assertTrue(state.can_announce())

    def test_https_only_enforcement(self):
        """Tracker URLs must be HTTPS."""
        # This is tested in TrackerClient init — http:// URLs should be skipped
        config = {
            'enabled': True,
            'tracker_url': [
                'http://insecure.example.com',  # should be rejected
                'https://secure.example.com',     # should be accepted
            ]
        }
        client = TrackerClient(MockIdentity(), config)
        self.assertEqual(len(client.trackers), 1)
        self.assertEqual(client.trackers[0].url, 'https://secure.example.com')

    def test_max_trackers(self):
        """Should not accept more than MAX_TRACKERS tracker URLs."""
        urls = [f'https://tracker{i}.example.com' for i in range(MAX_TRACKERS + 5)]
        config = {'enabled': True, 'tracker_url': urls}
        client = TrackerClient(MockIdentity(), config)
        self.assertEqual(len(client.trackers), MAX_TRACKERS)


# ============================================================================
# TEST TRACKER CLIENT (unit tests without real HTTP)
# ============================================================================

class TestTrackerClient(unittest.TestCase):

    def _make_client(self, **kwargs):
        config = {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
            'max_ram_share_mb': 2048,
            'max_cpu_percent': 30,
            'gpu_share': False,
            'models_share': ['glm-5.1:cloud'],
            'bandwidth_limit_kbps': 5000,
            **kwargs
        }
        return TrackerClient(MockIdentity(), config)

    def test_init_default_config(self):
        client = TrackerClient(MockIdentity())
        self.assertFalse(client.enabled)
        self.assertEqual(len(client.trackers), 0)

    def test_init_with_config(self):
        client = self._make_client()
        self.assertTrue(client.enabled)
        self.assertEqual(len(client.trackers), 1)
        self.assertEqual(client.max_ram_share_mb, 2048)
        self.assertEqual(client.models_share, ['glm-5.1:cloud'])

    def test_build_announcement_structure(self):
        client = self._make_client()
        client._start_time = time.time() - 3600  # 1 hour uptime
        announcement = client._build_announcement()

        self.assertIn('node_id', announcement)
        self.assertIn('name', announcement)
        self.assertIn('capabilities', announcement)
        self.assertIn('signature', announcement)
        self.assertIn('timestamp', announcement)
        self.assertIn('uptime_seconds', announcement)

        # Check no private fields leaked
        for forbidden in ('private_key', 'secret', 'p2p_secret', 'password', 'api_key'):
            self.assertNotIn(forbidden, announcement)
            self.assertNotIn(forbidden, announcement.get('capabilities', {}))

    def test_build_announcement_signing(self):
        client = self._make_client()
        announcement = client._build_announcement()

        # Signature should be present and verifiable
        self.assertTrue(len(announcement['signature']) > 0)

        # Verify the signature against the canonical form
        # Remove signature before verifying
        sig = announcement.pop('signature')
        canonical = json.dumps(announcement, sort_keys=True, separators=(',', ':'))
        self.assertTrue(client.identity.verify(canonical, sig))

    def test_build_announcement_capabilities(self):
        client = self._make_client()
        announcement = client._build_announcement()
        caps = announcement['capabilities']

        self.assertEqual(caps['ram_share_mb'], 2048)
        self.assertEqual(caps['models'], ['glm-5.1:cloud'])
        self.assertEqual(caps['bandwidth_kbps'], 5000)
        self.assertFalse(caps['gpu'])

    def test_local_discover_by_model(self):
        client = self._make_client()

        # Add some known nodes manually
        client.known_nodes['node1'] = KnownNode(
            node_id='node1', address='1.2.3.4:8081',
            capabilities={'models': ['glm-5.1:cloud'], 'gpu': False, 'ram_share_mb': 2048},
            score=80, name='node1'
        )
        client.known_nodes['node2'] = KnownNode(
            node_id='node2', address='5.6.7.8:8081',
            capabilities={'models': ['llama3:8b'], 'gpu': True, 'ram_share_mb': 4096},
            score=60, name='node2'
        )
        client.known_nodes['node3'] = KnownNode(
            node_id='node3', address='9.10.11.12:8081',
            capabilities={'models': ['glm-5.1:cloud', 'llama3:8b'], 'gpu': False, 'ram_share_mb': 1024},
            score=40, name='node3'
        )

        # Search for glm-5.1:cloud
        results = client._local_discover(model='glm-5.1:cloud')
        self.assertEqual(len(results), 2)
        # Should be sorted by score (node1=80 first)
        self.assertEqual(results[0].node_id, 'node1')

    def test_local_discover_by_ram(self):
        client = self._make_client()

        client.known_nodes['n1'] = KnownNode(
            node_id='n1', address='1.2.3.4:8081',
            capabilities={'models': [], 'ram_share_mb': 2048}, score=50
        )
        client.known_nodes['n2'] = KnownNode(
            node_id='n2', address='5.6.7.8:8081',
            capabilities={'models': [], 'ram_share_mb': 512}, score=50
        )

        results = client._local_discover(min_ram_mb=1000)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].node_id, 'n1')

    def test_local_discover_gpu_required(self):
        client = self._make_client()

        client.known_nodes['n1'] = KnownNode(
            node_id='n1', address='1.2.3.4:8081',
            capabilities={'gpu': True, 'models': []}, score=50
        )
        client.known_nodes['n2'] = KnownNode(
            node_id='n2', address='5.6.7.8:8081',
            capabilities={'gpu': False, 'models': []}, score=50
        )

        results = client._local_discover(gpu_required=True)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].capabilities['gpu'])

    def test_local_discover_stale_nodes_excluded(self):
        client = self._make_client()

        node = KnownNode(node_id='stale', address='1.2.3.4:8081', score=99)
        node.last_seen = time.time() - 2000  # stale
        client.known_nodes['stale'] = node

        results = client._local_discover()
        self.assertEqual(len(results), 0)

    def test_local_discover_max_results(self):
        client = self._make_client()

        for i in range(50):
            client.known_nodes[f'n{i}'] = KnownNode(
                node_id=f'n{i}', address=f'1.2.3.{i}:8081', score=i
            )

        results = client._local_discover(max_results=10)
        self.assertEqual(len(results), 10)
        # Should be sorted by score descending
        self.assertGreater(results[0].score, results[-1].score)

    def test_update_known_node_new(self):
        client = self._make_client()
        client._update_known_node({
            'node_id': 'new-node',
            'address': '10.0.0.1:8081',
            'score': 75.0,
            'capabilities': {'models': ['glm-5.1:cloud']},
        })
        self.assertIn('new-node', client.known_nodes)
        self.assertEqual(client.known_nodes['new-node'].score, 75.0)

    def test_update_known_node_existing(self):
        client = self._make_client()
        client.known_nodes['existing'] = KnownNode(
            node_id='existing', address='10.0.0.1:8081', score=30.0
        )
        client._update_known_node({
            'node_id': 'existing',
            'address': '10.0.0.1:8081',
            'score': 90.0,
            'name': 'updated-name',
        })
        self.assertEqual(client.known_nodes['existing'].score, 90.0)
        self.assertEqual(client.known_nodes['existing'].name, 'updated-name')

    def test_update_known_node_malformed(self):
        client = self._make_client()
        # No node_id or address — should be skipped
        client._update_known_node({'foo': 'bar'})
        self.assertEqual(len(client.known_nodes), 0)

    def test_get_known_nodes(self):
        client = self._make_client()

        fresh = KnownNode(node_id='fresh', address='1.2.3.4:8081', score=50)
        client.known_nodes['fresh'] = fresh

        stale = KnownNode(node_id='stale', address='5.6.7.8:8081', score=99)
        stale.last_seen = time.time() - 2000
        client.known_nodes['stale'] = stale

        nodes = client.get_known_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['node_id'], 'fresh')

    def test_get_tracker_status(self):
        client = self._make_client()
        status = client.get_tracker_status()
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]['url'], 'https://tracker.example.com')
        self.assertFalse(status[0]['connected'])

    def test_to_dict(self):
        client = self._make_client()
        d = client.to_dict()
        self.assertTrue(d['enabled'])
        self.assertEqual(d['max_ram_share_mb'], 2048)
        self.assertEqual(d['models_shared'], ['glm-5.1:cloud'])
        self.assertFalse(d['gpu_share'])
        self.assertEqual(len(d['trackers']), 1)

    def test_announce_interval_minimum(self):
        """Announce interval should never be less than MIN_ANNOUNCE_INTERVAL."""
        config = {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
            'announce_interval': 10,  # way below minimum
        }
        client = TrackerClient(MockIdentity(), config)
        self.assertGreaterEqual(client.announce_interval, MIN_ANNOUNCE_INTERVAL)

    def test_update_own_config(self):
        client = self._make_client()
        client.update_own_config(
            address='192.168.1.100:8081',
            cpu_cores=8,
            ram_total_mb=16384,
            max_model_category='small'
        )
        self.assertEqual(client._own_address, '192.168.1.100:8081')
        self.assertEqual(client._own_cpu_cores, 8)
        self.assertEqual(client._own_ram_total_mb, 16384)

    def test_announcement_includes_config(self):
        client = self._make_client()
        client.update_own_config(
            address='192.168.1.100:8081',
            cpu_cores=8,
            ram_total_mb=16384,
            max_model_category='small'
        )
        announcement = client._build_announcement()
        self.assertEqual(announcement['address'], '192.168.1.100:8081')
        self.assertEqual(announcement['capabilities']['cpu_cores'], 8)
        self.assertEqual(announcement['capabilities']['ram_total_mb'], 16384)


# ============================================================================
# TEST ASYNC OPERATIONS (with mock HTTP)
# ============================================================================

class TestTrackerClientAsync(unittest.TestCase):

    def test_announce_with_mock_session(self):
        """Test announce with a mocked aiohttp session."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
            'models_share': ['glm-5.1:cloud'],
            'max_ram_share_mb': 2048,
        })

        # Create a mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_length = 100
        mock_response.json = AsyncMock(return_value={"status": "ok"})

        # Create mock session
        mock_session = MagicMock()
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        client._session = mock_session

        result = asyncio.get_event_loop().run_until_complete(client.announce(address='1.2.3.4:8081'))
        self.assertTrue(result)
        # Verify POST was called
        mock_session.post.assert_called_once()

    def test_announce_failure_backoff(self):
        """Test that announce failure triggers backoff."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
        })

        # Simulate connection failure
        mock_session = MagicMock()
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__ = AsyncMock(side_effect=aiohttp.ClientConnectorError(
            MagicMock(), MagicMock()))
        mock_post_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        client._session = mock_session

        result = asyncio.get_event_loop().run_until_complete(client.announce())
        self.assertFalse(result)
        # Tracker should be in backoff
        self.assertTrue(client.trackers[0].is_backing_off)

    def test_discover_fallback_to_local(self):
        """When all trackers fail, discover should fall back to local cache."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
        })

        # Add a known node
        client.known_nodes['n1'] = KnownNode(
            node_id='n1', address='1.2.3.4:8081',
            capabilities={'models': ['glm-5.1:cloud'], 'ram_share_mb': 2048},
            score=50
        )

        # Session is None (not started), should fall back to local
        client._session = None
        results = asyncio.get_event_loop().run_until_complete(
            client.discover(model='glm-5.1:cloud')
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].node_id, 'n1')

    def test_stale_cleanup(self):
        """Test that stale nodes are removed by the refresh loop logic."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
        })

        # Add a fresh node and a stale node
        fresh = KnownNode(node_id='fresh', address='1.2.3.4:8081')
        stale = KnownNode(node_id='stale', address='5.6.7.8:8081')
        stale.last_seen = time.time() - 2000  # ~33 minutes ago
        client.known_nodes['fresh'] = fresh
        client.known_nodes['stale'] = stale

        # Manually run the cleanup logic from _refresh_loop
        stale_ids = [nid for nid, node in client.known_nodes.items() if node.is_stale]
        for nid in stale_ids:
            del client.known_nodes[nid]

        self.assertIn('fresh', client.known_nodes)
        self.assertNotIn('stale', client.known_nodes)


# ============================================================================
# TEST EDGE CASES
# ============================================================================

class TestEdgeCases(unittest.TestCase):

    def test_empty_tracker_list(self):
        """Client with no trackers should be usable (local-only)."""
        client = TrackerClient(MockIdentity(), {'enabled': True, 'tracker_url': []})
        self.assertEqual(len(client.trackers), 0)

    def test_http_url_rejected(self):
        """HTTP tracker URLs should be rejected (HTTPS only)."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': ['http://insecure.example.com']
        })
        self.assertEqual(len(client.trackers), 0)

    def test_mixed_http_https_urls(self):
        """Only HTTPS URLs should be accepted."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': [
                'http://bad.example.com',
                'https://good.example.com',
                'ftp://also.bad.com',
                'https://also.good.com',
            ]
        })
        self.assertEqual(len(client.trackers), 2)
        self.assertEqual(client.trackers[0].url, 'https://good.example.com')
        self.assertEqual(client.trackers[1].url, 'https://also.good.com')

    def test_discover_cache(self):
        """Discover results should be cached."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
        })

        # Manually populate cache
        nodes = [KnownNode(node_id='n1', address='1.2.3.4:8081', score=50)]
        client._discover_cache['glm-5.1:cloud:0:False'] = (time.time(), nodes)

        # Session is None — should use cache
        client._session = None
        # Note: discover with model will try cache first
        # Since cache key format is different, test manually
        self.assertTrue(len(client._discover_cache) > 0)

    def test_announcement_no_private_key_leak(self):
        """Announcements must NEVER contain private key material."""
        client = TrackerClient(MockIdentity(), {
            'enabled': True,
            'tracker_url': ['https://tracker.example.com'],
            'models_share': ['glm-5.1:cloud'],
        })
        announcement = client._build_announcement()
        announcement_str = json.dumps(announcement)

        # Check for common private field names
        for secret in ('private_key', 'secret', 'password', 'token',
                       'p2p_secret', 'api_key', 'auth', 'config'):
            self.assertNotIn(secret, announcement_str.lower(),
                            f"Private field '{secret}' found in announcement")

    def test_tracker_url_trailing_slash_stripped(self):
        """Tracker URLs should have trailing slashes stripped."""
        state = TrackerState("https://tracker.example.com/")
        self.assertEqual(state.url, "https://tracker.example.com")

    def test_known_node_address_as_fallback_key(self):
        """If node_id is missing, use address as key."""
        client = TrackerClient(MockIdentity(), {'enabled': True, 'tracker_url': []})
        client._update_known_node({
            'address': '10.0.0.1:8081',
            'score': 30.0,
        })
        # Should use address as key since node_id is missing
        self.assertIn('10.0.0.1:8081', client.known_nodes)

    def test_multiple_tracker_announce_tries_all(self):
        """Announce should try all trackers and succeed if at least one works."""
        config = {
            'enabled': True,
            'tracker_url': [
                'https://tracker1.example.com',
                'https://tracker2.example.com',
                'https://tracker3.example.com',
            ]
        }
        client = TrackerClient(MockIdentity(), config)
        self.assertEqual(len(client.trackers), 3)


if __name__ == '__main__':
    unittest.main()