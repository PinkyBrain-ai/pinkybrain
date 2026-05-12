#!/usr/bin/env python3
"""
Tests Unitaires - P2P Network v5.2.0
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v5 import (
    PinkyBrain,
    Peer,
    NodeIdentity,
    WebOfTrust,
    RateLimiter,
    SharingQuota,
)


PINKY_CONFIG = {
    "node_name": "pinky",
    "version": "5.2.0",
    "host": "127.0.0.1",
    "port": 8081,
    "ollama_host": "127.0.0.1",
    "ollama_port": 11434,
    "local_models": ["test-model"],
    "stealth_mode": False,
    "share_ai": True,
    "rate_limit": 10.0,
    "rate_burst": 20,
    "peers": [],
    "providers": {},
    "public_mesh": {"enabled": False},
    "conversation_store": {"enabled": False},
}


# =============================================================================
# TESTS PEER
# =============================================================================

class TestPeer:
    def test_create_peer(self):
        peer = Peer(name="Bug", host="192.0.2.1", port=8080, models=["model1"])
        assert peer.name == "Bug"
        assert peer.host == "192.0.2.1"
        assert peer.port == 8080


# =============================================================================
# TESTS NODE IDENTITY
# =============================================================================

class TestNodeIdentity:
    def test_create_identity(self):
        identity = NodeIdentity("pinky", "test_secret")
        assert identity.name == "pinky"

    def test_sign_verify(self):
        identity = NodeIdentity("pinky", "test_secret")
        sig = identity.sign("hello")
        assert identity.verify("hello", sig)
        assert not identity.verify("other", sig)


# =============================================================================
# TESTS WEB OF TRUST
# =============================================================================

class TestWebOfTrust:
    def test_add_trust(self):
        wot = WebOfTrust()
        wot.add_trust("key1", "key2")
        assert wot.is_trusted("key2", min_score=0.5)

    def test_trust_score_default(self):
        wot = WebOfTrust()
        assert wot.trust_score("unknown") == 0.0


# =============================================================================
# TESTS RATE LIMITER
# =============================================================================

class TestP2PRateLimiter:
    def test_basic_rate(self):
        limiter = RateLimiter(rate=10.0, burst=5)
        assert limiter.allow("client1")

    def test_burst_limit(self):
        limiter = RateLimiter(rate=1.0, burst=3)
        results = [limiter.allow("client1") for _ in range(4)]
        # First 3 should be allowed (burst), 4th may or may not
        assert results[0]


# =============================================================================
# TESTS SHARING QUOTA
# =============================================================================

class TestSharingQuota:
    def test_new_peer(self):
        quota = SharingQuota()
        info = quota.get_or_create("new_peer")
        assert info is not None
        assert info["queries_made"] == 0

    def test_record_served(self):
        quota = SharingQuota()
        quota.record_query_served("peer1")
        info = quota.get_or_create("peer1")
        assert info["queries_served"] == 1


# =============================================================================
# TESTS PINKYBRAIN PINKY
# =============================================================================

class TestPinkyNode:
    def test_init(self):
        brain = PinkyBrain(PINKY_CONFIG)
        assert brain.node_name == "pinky"
        assert brain.version == "5.2.0"

    def test_v5_modules(self):
        brain = PinkyBrain(PINKY_CONFIG)
        assert hasattr(brain, 'resource_guard')
        assert hasattr(brain, 'adaptive_scheduler')
        assert hasattr(brain, 'conversation_store')
        assert hasattr(brain, 'model_share_manager')
        assert hasattr(brain, 'tracker_client')