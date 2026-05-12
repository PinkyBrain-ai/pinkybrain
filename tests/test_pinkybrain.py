#!/usr/bin/env python3
"""
Tests Unitaires - PinkyBrain v5.2.0
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v5 import (
    PinkyBrain,
    Peer,
    RateLimiter,
    SharingQuota,
    CircuitBreaker,
    NodeIdentity,
    VectorClock,
    CRDTMemory,
    ModelRouter,
)


# =============================================================================
# CONFIG DE TEST
# =============================================================================

TEST_CONFIG = {
    "node_name": "test_node",
    "version": "5.2.0",
    "host": "127.0.0.1",
    "port": 18080,
    "ollama_host": "127.0.0.1",
    "ollama_port": 11434,
    "local_models": ["test-model:latest"],
    "stealth_mode": False,
    "share_ai": False,
    "rate_limit": 100.0,
    "rate_burst": 200,
    "peers": [],
    "providers": {},
    "public_mesh": {"enabled": False},
    "conversation_store": {"enabled": False},
}


# =============================================================================
# TESTS NODE IDENTITY
# =============================================================================

class TestNodeIdentity:
    def test_create_identity(self):
        identity = NodeIdentity("test_node", "test_secret")
        assert identity.name == "test_node"
        assert identity.fingerprint is not None

    def test_sign_and_verify(self):
        identity = NodeIdentity("test_node", "test_secret")
        message = "test_message"
        signature = identity.sign(message)
        assert identity.verify(message, signature)

    def test_verify_wrong_message(self):
        identity = NodeIdentity("test_node", "test_secret")
        signature = identity.sign("message1")
        assert not identity.verify("message2", signature)


# =============================================================================
# TESTS RATE LIMITER
# =============================================================================

class TestRateLimiter:
    def test_allow_within_limit(self):
        limiter = RateLimiter(rate=100.0, burst=10)
        assert limiter.allow("client1")

    def test_allow_burst(self):
        limiter = RateLimiter(rate=1.0, burst=5)
        results = [limiter.allow("client1") for _ in range(5)]
        assert all(results)


# =============================================================================
# TESTS CIRCUIT BREAKER
# =============================================================================

class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker()
        assert cb.can_execute()

    def test_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert not cb.can_execute()


# =============================================================================
# TESTS VECTOR CLOCK
# =============================================================================

class TestVectorClock:
    def test_increment(self):
        vc = VectorClock("node1")
        vc.increment()
        assert vc.clocks.get("node1") == 1

    def test_merge(self):
        vc1 = VectorClock("node1")
        vc1.increment()
        vc2 = VectorClock("node2")
        vc2.increment()
        vc1.merge(vc2.clocks)
        assert vc1.clocks.get("node2") == 1


# =============================================================================
# TESTS CRDT MEMORY
# =============================================================================

class TestCRDTMemory:
    def test_set_and_get(self):
        mem = CRDTMemory("node1", max_size=100, default_ttl=3600)
        mem.set("key1", "value1")
        assert mem.get("key1") == "value1"

    def test_delete(self):
        mem = CRDTMemory("node1")
        mem.set("key1", "value1")
        assert mem.delete("key1")
        assert mem.get("key1") is None


# =============================================================================
# TESTS SHARING QUOTA
# =============================================================================

class TestSharingQuota:
    def test_get_or_create(self):
        quota = SharingQuota()
        info = quota.get_or_create("peer1")
        assert info["queries_made"] == 0

    def test_record_query(self):
        quota = SharingQuota()
        quota.record_query_served("peer1")
        info = quota.get_or_create("peer1")
        assert info["queries_served"] == 1


# =============================================================================
# TESTS PINKYBRAIN INIT
# =============================================================================

class TestPinkyBrainInit:
    def test_init_with_config(self):
        brain = PinkyBrain(TEST_CONFIG)
        assert brain.node_name == "test_node"
        assert brain.version == "5.2.0"
        assert brain.port == 18080

    def test_has_v5_modules(self):
        brain = PinkyBrain(TEST_CONFIG)
        # Check v5 module attributes exist (may be None if not installed)
        assert hasattr(brain, 'resource_guard')
        assert hasattr(brain, 'adaptive_scheduler')
        assert hasattr(brain, 'conversation_store')
        assert hasattr(brain, 'model_share_manager')
        assert hasattr(brain, 'tracker_client')

    def test_status_includes_v5(self):
        brain = PinkyBrain(TEST_CONFIG)
        status = brain.get_status()
        assert "resource_guard" in status
        assert "adaptive_scheduler" in status
        assert "conversation_store" in status
        assert "model_share_manager" in status
        assert "tracker_client" in status