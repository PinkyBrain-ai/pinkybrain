#!/usr/bin/env python3
"""
Tests Unitaires - PinkyBrain v5.2.0 (via PinkyBrain profile)
PinkyBrain is now a profile of PinkyBrain
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pinkybrain_v5 import (
    PinkyBrain,
    NodeIdentity,
    RateLimiter,
    CircuitBreaker,
)

BUG_CONFIG = {
    "node_name": "bug",
    "version": "5.2.0",
    "host": "127.0.0.1",
    "port": 8080,
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


class TestPinkyBrainIdentity:
    """Test Bug node identity"""

    def test_bug_identity(self):
        identity = NodeIdentity("bug", "bug-secret")
        assert identity.name == "bug"
        assert identity.fingerprint is not None

    def test_bug_signing(self):
        identity = NodeIdentity("bug", "bug-secret")
        sig = identity.sign("test_message")
        assert identity.verify("test_message", sig)


class TestPinkyBrainComponents:
    """Test Bug-specific components"""

    def test_rate_limiter(self):
        limiter = RateLimiter(rate=10.0, burst=20)
        assert limiter.allow("test_client")

    def test_circuit_breaker(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)
        assert cb.can_execute()
        for _ in range(3):
            cb.record_failure()
        assert not cb.can_execute()


class TestPinkyBrainInit:
    """Test Bug as PinkyBrain node"""

    def test_init(self):
        brain = PinkyBrain(BUG_CONFIG)
        assert brain.node_name == "bug"
        assert brain.version == "5.2.0"
        assert brain.share_ai is True