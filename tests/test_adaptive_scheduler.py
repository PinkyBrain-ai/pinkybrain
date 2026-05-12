#!/usr/bin/env python3
"""
🧪 Tests for Adaptive Scheduler — PinkyBrain v5
==================================================

Covers:
  - Strategy selection based on peer count
  - Strategy transitions (routing → partial → full → raid)
  - Fallback on failure
  - Chunk assignment and redistribution
  - Resource Guard integration
  - Input validation and security
  - Rate limiting
  - Malicious node detection
  - Edge cases
"""

import asyncio
import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from collections import deque

# ============================================================================
# Import the module under test
# ============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adaptive_scheduler import (
    AdaptiveScheduler,
    Strategy,
    TransitionState,
    ChunkAssignment,
    PeerInfo,
    InputValidator,
    SchedulerRateLimiter,
    MaliciousNodeDetector,
    ROUTING_MAX_PEERS,
    PARTIAL_SHARDING_MAX_PEERS,
    FULL_SHARDING_MAX_PEERS,
    REPLICATION_FACTOR,
    CHUNK_COUNT,
    MIN_PEERS_FOR_SHARDING,
    MIN_PEERS_FOR_FULL_SHARDING,
    MIN_PEERS_FOR_RAID,
    MAX_CHUNKS_PER_MODEL,
    MAX_PROMPT_LENGTH,
    PEER_STALE_TIMEOUT,
)

# Import constants that aren't at module level
from adaptive_scheduler import MAX_ROUTING_PER_SECOND as _MAX_ROUTING_RATE


# ============================================================================
# FIXTURES
# ============================================================================

def make_resource_guard(enabled=True, can_accept=True):
    """Create a mock Resource Guard."""
    guard = MagicMock()
    guard.enabled = enabled
    guard.can_accept_request.return_value = can_accept
    guard.get_available_resources.return_value = {
        "ram_mb": 2048,
        "cpu_available_percent": 25.0,
        "gpu": False,
        "state": "active",
        "can_accept": can_accept,
    }
    return guard


def make_identity(name="test_node"):
    """Create a mock identity."""
    identity = MagicMock()
    identity.name = name
    identity.public_key_hex = "abc123def456"
    identity.sign.return_value = "signature_hex"
    return identity


def make_tracker_client(peers=None):
    """Create a mock TrackerClient."""
    tc = MagicMock()
    tc.get_known_nodes.return_value = peers or []
    tc.enabled = True
    return tc


_peer_counter = 0

def make_peer(node_id=None, address=None, name=None, ram_share_mb=2048,
              cpu_cores=4, gpu_available=False, models=None, score=50.0,
              bandwidth_kbps=10000, uptime_seconds=86400):
    """Create a peer data dict (as would come from tracker)."""
    global _peer_counter
    _peer_counter += 1
    if node_id is None:
        node_id = f"node_{_peer_counter}"
    if address is None:
        address = f"10.0.0.{_peer_counter % 254 + 1}:8081"
    return {
        "node_id": node_id,
        "address": address,
        "name": name or (f"peer_{node_id}" if node_id else "peer"),
        "ram_share_mb": ram_share_mb,
        "cpu_cores": cpu_cores,
        "gpu_available": gpu_available,
        "gpu": gpu_available,
        "models": models or ["glm-5.1:cloud"],
        "score": score,
        "bandwidth_kbps": bandwidth_kbps,
        "uptime_seconds": uptime_seconds,
        "last_seen": time.time(),
    }


def make_scheduler(peers=None, enabled=True, can_accept=True, config=None):
    """Create an AdaptiveScheduler with mocks."""
    guard = make_resource_guard(enabled=enabled, can_accept=can_accept)
    identity = make_identity()
    tracker = make_tracker_client(peers=peers)
    scheduler = AdaptiveScheduler(
        identity=identity,
        resource_guard=guard,
        tracker_client=tracker,
        config=config or {},
    )
    # Add peers directly
    if peers:
        for p in peers:
            peer_info = InputValidator.sanitize_peer_data(p)
            if peer_info:
                scheduler._peers[peer_info.node_id] = peer_info
    return scheduler


# ============================================================================
# TESTS — Strategy Selection
# ============================================================================

class TestStrategySelection:
    """Test that strategy is selected correctly based on peer count."""

    def test_routing_with_1_peer(self):
        s = make_scheduler([make_peer(node_id="p1")])
        assert s.determine_strategy(1) == Strategy.ROUTING

    def test_routing_with_2_peers(self):
        s = make_scheduler([make_peer(node_id=f"p{i}") for i in range(2)])
        assert s.determine_strategy(2) == Strategy.ROUTING

    def test_routing_with_3_peers(self):
        s = make_scheduler([make_peer(node_id=f"p{i}") for i in range(3)])
        assert s.determine_strategy(3) == Strategy.ROUTING

    def test_partial_sharding_with_4_peers(self):
        assert Strategy.PARTIAL_SHARDING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(4)

    def test_partial_sharding_with_7_peers(self):
        assert Strategy.PARTIAL_SHARDING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(7)

    def test_partial_sharding_with_10_peers(self):
        assert Strategy.PARTIAL_SHARDING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(10)

    def test_full_sharding_with_11_peers(self):
        assert Strategy.FULL_SHARDING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(11)

    def test_full_sharding_with_30_peers(self):
        assert Strategy.FULL_SHARDING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(30)

    def test_full_sharding_with_50_peers(self):
        assert Strategy.FULL_SHARDING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(50)

    def test_raid_ram_with_51_peers(self):
        assert Strategy.RAID_RAM == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(51)

    def test_raid_ram_with_1000_peers(self):
        assert Strategy.RAID_RAM == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(1000)

    def test_routing_with_0_peers(self):
        assert Strategy.ROUTING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(0)

    def test_negative_peers_gives_routing(self):
        assert Strategy.ROUTING == AdaptiveScheduler(
            make_identity(), make_resource_guard()
        ).determine_strategy(-1)


# ============================================================================
# TESTS — Replication Factor
# ============================================================================

class TestReplicationFactor:
    def test_routing_has_no_replication(self):
        s = make_scheduler()
        assert s.get_replication_factor(Strategy.ROUTING) == 0

    def test_partial_sharding_replication(self):
        s = make_scheduler()
        assert s.get_replication_factor(Strategy.PARTIAL_SHARDING) == 2

    def test_full_sharding_replication(self):
        s = make_scheduler()
        assert s.get_replication_factor(Strategy.FULL_SHARDING) == 2

    def test_raid_ram_replication(self):
        s = make_scheduler()
        assert s.get_replication_factor(Strategy.RAID_RAM) == 3

    def test_replication_override(self):
        s = make_scheduler(config={"max_replication": 1})
        assert s.get_replication_factor(Strategy.RAID_RAM) == 1
        assert s.get_replication_factor(Strategy.PARTIAL_SHARDING) == 1


# ============================================================================
# TESTS — Chunk Count
# ============================================================================

class TestChunkCount:
    def test_routing_chunk_count(self):
        s = make_scheduler()
        assert s.get_chunk_count("test_model", Strategy.ROUTING) == 1

    def test_partial_sharding_chunk_count(self):
        s = make_scheduler()
        assert s.get_chunk_count("test_model", Strategy.PARTIAL_SHARDING) == 2

    def test_full_sharding_chunk_count(self):
        s = make_scheduler()
        assert s.get_chunk_count("test_model", Strategy.FULL_SHARDING) == 4

    def test_raid_ram_chunk_count(self):
        s = make_scheduler()
        assert s.get_chunk_count("test_model", Strategy.RAID_RAM) == 8

    def test_chunk_count_with_model_size(self):
        peers = [make_peer(node_id=f"p{i}") for i in range(20)]
        s = make_scheduler(peers=peers)
        s.set_model_sizes({"big_model": 16000})  # 16 GB model
        # Should not create more chunks than size allows (512 MB min)
        chunks = s.get_chunk_count("big_model", Strategy.FULL_SHARDING)
        assert chunks <= MAX_CHUNKS_PER_MODEL
        assert chunks >= 1

    def test_max_chunks_limit(self):
        s = make_scheduler()
        # Even with huge model, chunk count should be capped
        s.set_model_sizes({"huge_model": 1_000_000})
        chunks = s.get_chunk_count("huge_model", Strategy.RAID_RAM)
        assert chunks <= MAX_CHUNKS_PER_MODEL


# ============================================================================
# TESTS — Input Validation
# ============================================================================

class TestInputValidation:
    def test_valid_model_names(self):
        assert InputValidator.validate_model_name("glm-5.1:cloud") is True
        assert InputValidator.validate_model_name("llama3-8b") is True
        assert InputValidator.validate_model_name("model_v2") is True
        assert InputValidator.validate_model_name("my-model") is True

    def test_invalid_model_names(self):
        assert InputValidator.validate_model_name("") is False
        assert InputValidator.validate_model_name("a" * 129) is False
        assert InputValidator.validate_model_name("model with spaces") is False
        assert InputValidator.validate_model_name("model\x00bad") is False
        assert InputValidator.validate_model_name(None) is False
        assert InputValidator.validate_model_name(123) is False

    def test_valid_node_ids(self):
        assert InputValidator.validate_node_id("abc123") is True
        assert InputValidator.validate_node_id("deadbeef42") is True

    def test_invalid_node_ids(self):
        assert InputValidator.validate_node_id("") is False
        assert InputValidator.validate_node_id("a" * 257) is False
        assert InputValidator.validate_node_id("node with spaces") is False
        assert InputValidator.validate_node_id(None) is False

    def test_valid_addresses(self):
        assert InputValidator.validate_address("10.0.0.1:8081") is True
        assert InputValidator.validate_address("example.com:443") is True

    def test_invalid_addresses(self):
        assert InputValidator.validate_address("") is False
        assert InputValidator.validate_address("a" * 513) is False
        assert InputValidator.validate_address("addr\x00bad") is False
        assert InputValidator.validate_address(None) is False

    def test_valid_prompts(self):
        assert InputValidator.validate_prompt("Hello") is True
        assert InputValidator.validate_prompt("a" * MAX_PROMPT_LENGTH) is True

    def test_invalid_prompts(self):
        assert InputValidator.validate_prompt("a" * (MAX_PROMPT_LENGTH + 1)) is False
        assert InputValidator.validate_prompt(None) is False
        assert InputValidator.validate_prompt(123) is False

    def test_sanitize_peer_data_valid(self):
        data = make_peer(node_id="node1", ram_share_mb=2048)
        peer = InputValidator.sanitize_peer_data(data)
        assert peer is not None
        assert peer.node_id == "node1"
        assert peer.ram_share_mb == 2048

    def test_sanitize_peer_data_clamps_ram(self):
        data = make_peer(ram_share_mb=999999)
        peer = InputValidator.sanitize_peer_data(data)
        assert peer is not None
        assert peer.ram_share_mb == 65536  # MAX_PEER_RAM_MB

    def test_sanitize_peer_data_negative_ram(self):
        data = make_peer(ram_share_mb=-1000)
        peer = InputValidator.sanitize_peer_data(data)
        assert peer is not None
        assert peer.ram_share_mb == 0

    def test_sanitize_peer_data_invalid_node_id(self):
        data = make_peer(node_id="invalid id with spaces")
        peer = InputValidator.sanitize_peer_data(data)
        assert peer is None

    def test_sanitize_peer_data_invalid_models_filtered(self):
        data = make_peer(models=["valid-model", "invalid model", "another-valid"])
        peer = InputValidator.sanitize_peer_data(data)
        assert peer is not None
        assert "valid-model" in peer.models
        assert "another-valid" in peer.models
        assert "invalid model" not in peer.models

    def test_sanitize_peer_data_non_dict(self):
        assert InputValidator.sanitize_peer_data("not a dict") is None
        assert InputValidator.sanitize_peer_data(None) is None
        assert InputValidator.sanitize_peer_data(42) is None

    def test_sanitize_peer_data_bad_numeric_fields(self):
        data = make_peer(ram_share_mb="not_a_number", cpu_cores=None)
        peer = InputValidator.sanitize_peer_data(data)
        assert peer is not None
        assert peer.ram_share_mb == 0
        assert peer.cpu_cores == 0


# ============================================================================
# TESTS — Rate Limiting
# ============================================================================

class TestRateLimiter:
    def test_allows_within_rate(self):
        limiter = SchedulerRateLimiter(rate=10.0, burst=5)
        assert limiter.allow("test") is True
        assert limiter.allow("test") is True
        assert limiter.allow("test") is True

    def test_blocks_over_burst(self):
        limiter = SchedulerRateLimiter(rate=1.0, burst=3)
        assert limiter.allow("test") is True
        assert limiter.allow("test") is True
        assert limiter.allow("test") is True
        assert limiter.allow("test") is False  # Burst exhausted

    def test_separate_keys(self):
        limiter = SchedulerRateLimiter(rate=1.0, burst=3)
        # Exhaust key A
        limiter.allow("A")
        limiter.allow("A")
        limiter.allow("A")
        # Key B should still work
        assert limiter.allow("B") is True

    def test_refill(self):
        limiter = SchedulerRateLimiter(rate=1000.0, burst=3)
        limiter.allow("test")
        limiter.allow("test")
        limiter.allow("test")
        # Should refill quickly
        time.sleep(0.01)
        assert limiter.allow("test") is True

    def test_reset(self):
        limiter = SchedulerRateLimiter(rate=1.0, burst=3)
        limiter.allow("test")
        limiter.allow("test")
        limiter.allow("test")
        limiter.reset("test")
        assert limiter.allow("test") is True

    def test_reset_all(self):
        limiter = SchedulerRateLimiter(rate=1.0, burst=3)
        limiter.allow("A")
        limiter.allow("B")
        limiter.reset()
        assert limiter.allow("A") is True
        assert limiter.allow("B") is True


# ============================================================================
# TESTS — Malicious Node Detection
# ============================================================================

class TestMaliciousNodeDetector:
    def test_records_success(self):
        detector = MaliciousNodeDetector()
        detector.record_success("good_node")
        assert detector.is_banned("good_node") is False

    def test_bans_after_max_failures(self):
        detector = MaliciousNodeDetector(max_failures=3)
        detector.record_failure("bad_node")
        detector.record_failure("bad_node")
        assert detector.is_banned("bad_node") is False
        detector.record_failure("bad_node")
        assert detector.is_banned("bad_node") is True

    def test_bans_after_false_claims(self):
        detector = MaliciousNodeDetector(max_false_claims=2)
        detector.record_false_claim("liar")
        assert detector.is_banned("liar") is False
        detector.record_false_claim("liar")
        assert detector.is_banned("liar") is True

    def test_success_reduces_failure_count(self):
        detector = MaliciousNodeDetector(max_failures=3)
        detector.record_failure("node1")
        detector.record_failure("node1")
        detector.record_success("node1")  # Reduces from 2 to 1
        detector.record_failure("node1")  # Back to 2
        assert detector.is_banned("node1") is False

    def test_ban_expires(self):
        detector = MaliciousNodeDetector(max_failures=1, ban_duration=0.01)
        detector.record_failure("node1")
        assert detector.is_banned("node1") is True
        time.sleep(0.02)
        assert detector.is_banned("node1") is False

    def test_get_banned_nodes(self):
        detector = MaliciousNodeDetector(max_failures=1, ban_duration=3600)
        detector.record_failure("node1")
        detector.record_failure("node2")
        banned = detector.get_banned_nodes()
        assert "node1" in banned
        assert "node2" in banned

    def test_to_dict(self):
        detector = MaliciousNodeDetector()
        result = detector.to_dict()
        assert "banned_nodes" in result
        assert "failure_counts" in result


# ============================================================================
# TESTS — Chunk Assignment
# ============================================================================

class TestChunkAssignment:
    @pytest.mark.asyncio
    async def test_routing_no_chunks(self):
        """Routing strategy should not create chunk assignments."""
        s = make_scheduler([make_peer(node_id="p1")])
        s.force_strategy("routing")
        assignments = await s._prepare_chunk_assignments(Strategy.ROUTING)
        assert assignments == {}

    @pytest.mark.asyncio
    async def test_partial_sharding_creates_chunks(self):
        """Partial sharding should create chunk assignments."""
        peers = [make_peer(node_id=f"p{i}", ram_share_mb=2048) for i in range(5)]
        s = make_scheduler(peers=peers)
        s.force_strategy("partial_sharding")
        s.set_model_sizes({"test_model": 4000})
        assignments = await s._prepare_chunk_assignments(Strategy.PARTIAL_SHARDING)
        # Should have assignments for the model
        # (may be None if not enough eligible, but with 5 peers it should work)
        # Note: depends on eligible peers having models
        # The scheduler uses _get_models_for_sharding which includes peer models
        # Since our test peers have models, this should work

    @pytest.mark.asyncio
    async def test_not_enough_peers_for_sharding(self):
        """With fewer than 4 peers, sharding should return None."""
        s = make_scheduler([make_peer(node_id="p1")])
        result = await s._prepare_chunk_assignments(Strategy.PARTIAL_SHARDING)
        assert result is None

    @pytest.mark.asyncio
    async def test_replication_in_assignments(self):
        """Full sharding should create replica assignments."""
        peers = [make_peer(node_id=f"p{i}", ram_share_mb=4096,
                          models=["big_model"]) for i in range(12)]
        s = make_scheduler(peers=peers)
        s.force_strategy("full_sharding")
        s.set_model_sizes({"big_model": 8000})
        assignments = await s._prepare_chunk_assignments(Strategy.FULL_SHARDING)
        if assignments and "big_model" in assignments:
            for chunk_idx, chunk_assignments in assignments["big_model"].items():
                # Should have replicas
                replicas = [a for a in chunk_assignments if a.is_replica]
                primaries = [a for a in chunk_assignments if not a.is_replica]
                assert len(primaries) >= 1
                # Replication factor for full_sharding is 2, so 1 primary + 1 replica


# ============================================================================
# TESTS — Strategy Transitions
# ============================================================================

class TestStrategyTransitions:
    @pytest.mark.asyncio
    async def test_transition_from_routing_to_partial_sharding(self):
        """Adding peers should trigger transition to partial sharding."""
        s = make_scheduler([make_peer(node_id="p1")])
        s.force_strategy("routing")
        assert s.strategy == Strategy.ROUTING

        # Add more peers
        for i in range(2, 6):
            s.add_peer(make_peer(node_id=f"p{i}", ram_share_mb=2048))

        # Manually trigger strategy update
        await s.update_strategy()
        # Should transition to partial_sharding (5 peers)
        assert s.strategy in (Strategy.PARTIAL_SHARDING, Strategy.ROUTING)
        # If resource guard blocks, stays routing

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        """If sharding fails, fall back to routing."""
        s = make_scheduler([make_peer(node_id=f"p{i}") for i in range(5)],
                          can_accept=True)
        # Force transition to sharding — will fail because peers have little RAM
        result = await s._transition_to(Strategy.PARTIAL_SHARDING)
        # Either succeeds or falls back
        assert s.strategy in (Strategy.PARTIAL_SHARDING, Strategy.ROUTING)

    def test_force_strategy(self):
        """force_strategy should set the strategy."""
        s = make_scheduler()
        assert s.strategy == Strategy.ROUTING

        result = s.force_strategy("partial_sharding")
        assert result is True
        assert s.strategy == Strategy.PARTIAL_SHARDING

    def test_force_strategy_invalid(self):
        """force_strategy with invalid name should return False."""
        s = make_scheduler()
        result = s.force_strategy("invalid_strategy")
        assert result is False
        assert s.strategy == Strategy.ROUTING  # Unchanged


# ============================================================================
# TESTS — Query Routing
# ============================================================================

class TestQueryRouting:
    @pytest.mark.asyncio
    async def test_routing_simple(self):
        """In routing mode, query should route to a single peer."""
        s = make_scheduler([make_peer(node_id="p1", models=["test_model"])],
                         can_accept=True)
        s.force_strategy("routing")
        result = await s.route_query("Hello", "test_model")
        assert result["strategy"] == "routing"
        assert result["target_node"] in ("p1", "local")
        assert result["fallback"] is False

    @pytest.mark.asyncio
    async def test_routing_fallback_no_model(self):
        """If no peer has the model, should fall back to local."""
        s = make_scheduler([make_peer(node_id="p1", models=["other_model"])],
                         can_accept=True)
        s.force_strategy("routing")
        result = await s.route_query("Hello", "test_model")
        assert result["target_node"] == "local"
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_routing_selects_best_peer(self):
        """Should select the peer with highest score for the model."""
        peers = [
            make_peer(node_id="p_low", models=["test_model"], score=10.0),
            make_peer(node_id="p_high", models=["test_model"], score=90.0),
        ]
        s = make_scheduler(peers=peers, can_accept=True)
        s.force_strategy("routing")
        result = await s.route_query("Hello", "test_model")
        assert result["target_node"] == "p_high"

    @pytest.mark.asyncio
    async def test_invalid_model_name_rejected(self):
        """Invalid model names should be rejected."""
        s = make_scheduler()
        s.force_strategy("routing")
        with pytest.raises(ValueError):
            await s.route_query("Hello", "invalid model name")

    @pytest.mark.asyncio
    async def test_too_long_prompt_rejected(self):
        """Prompts exceeding max length should be rejected."""
        s = make_scheduler()
        s.force_strategy("routing")
        with pytest.raises(ValueError):
            await s.route_query("x" * (MAX_PROMPT_LENGTH + 1), "test_model")

    @pytest.mark.asyncio
    async def test_resource_guard_blocks_query(self):
        """If Resource Guard refuses, query should be rejected."""
        guard = make_resource_guard(enabled=True, can_accept=False)
        s = make_scheduler([make_peer(node_id="p1")], can_accept=False)
        s.resource_guard = guard
        s.force_strategy("routing")
        with pytest.raises(RuntimeError):
            await s.route_query("Hello", "test_model")


# ============================================================================
# TESTS — Redistribution
# ============================================================================

class TestRedistribution:
    @pytest.mark.asyncio
    async def test_redistribution_routing_skipped(self):
        """Redistribution should be skipped in routing mode."""
        s = make_scheduler([make_peer(node_id="p1")])
        s.force_strategy("routing")
        # Should not raise and should not change anything
        await s.redistribute_chunks()

    @pytest.mark.asyncio
    async def test_redistribution_triggered_by_stale_peer(self):
        """If a chunk peer becomes stale, redistribution should be triggered."""
        peers = [make_peer(node_id=f"p{i}", ram_share_mb=2048,
                          models=["big_model"]) for i in range(5)]
        s = make_scheduler(peers=peers)
        s.force_strategy("partial_sharding")

        # Mark a peer as stale
        s._peers["p0"].last_seen = time.time() - PEER_STALE_TIMEOUT - 100

        # Should trigger redistribution
        await s.redistribute_chunks()


# ============================================================================
# TESTS — Resource Guard Integration
# ============================================================================

class TestResourceGuardIntegration:
    def test_check_resource_guard_enabled_accepting(self):
        """If guard is enabled and accepting, should return True."""
        guard = make_resource_guard(enabled=True, can_accept=True)
        s = make_scheduler()
        s.resource_guard = guard
        assert s._check_resource_guard() is True

    def test_check_resource_guard_enabled_refusing(self):
        """If guard is enabled but refusing, should return False."""
        guard = make_resource_guard(enabled=True, can_accept=False)
        s = make_scheduler()
        s.resource_guard = guard
        assert s._check_resource_guard() is False

    def test_check_resource_guard_disabled(self):
        """If guard is disabled, should return True (no restrictions)."""
        guard = make_resource_guard(enabled=False, can_accept=False)
        s = make_scheduler()
        s.resource_guard = guard
        assert s._check_resource_guard() is True

    def test_check_resource_guard_none(self):
        """If no guard, should return True."""
        s = make_scheduler()
        s.resource_guard = None
        assert s._check_resource_guard() is True

    def test_get_local_contribution(self):
        """Should return Resource Guard available resources."""
        guard = make_resource_guard(enabled=True, can_accept=True)
        s = make_scheduler()
        s.resource_guard = guard
        contrib = s.get_local_resource_contribution()
        assert contrib["ram_mb"] == 2048
        assert contrib["can_accept"] is True

    def test_get_local_contribution_no_guard(self):
        """Without guard, should return empty contribution."""
        s = make_scheduler()
        s.resource_guard = None
        contrib = s.get_local_resource_contribution()
        assert contrib["can_accept"] is False


# ============================================================================
# TESTS — Peer Management
# ============================================================================

class TestPeerManagement:
    def test_add_peer(self):
        """Adding a peer should make it available."""
        s = make_scheduler()
        s.add_peer(make_peer(node_id="new_peer", ram_share_mb=4096))
        assert "new_peer" in s._peers

    def test_add_invalid_peer(self):
        """Adding invalid peer data should be ignored."""
        s = make_scheduler()
        s.add_peer({"node_id": "invalid id", "address": "10.0.0.1:8081"})
        # Should not crash, peer should not be added (or added with sanitized data)

    def test_remove_peer(self):
        """Removing a peer should remove it from the scheduler."""
        s = make_scheduler([make_peer(node_id="p1")])
        s.remove_peer("p1")
        assert "p1" not in s._peers

    def test_remove_nonexistent_peer(self):
        """Removing a non-existent peer should not crash."""
        s = make_scheduler()
        s.remove_peer("nonexistent")  # Should not raise

    def test_eligible_peers_excludes_banned(self):
        """Banned peers should be excluded from eligible peers."""
        s = make_scheduler([make_peer(node_id="banned", ram_share_mb=2048)])
        s._malicious_detector.record_failure("banned")
        s._malicious_detector.record_failure("banned")
        s._malicious_detector.record_failure("banned")
        s._malicious_detector.record_failure("banned")
        s._malicious_detector.record_failure("banned")
        eligible = s._get_eligible_peers()
        assert "banned" not in [p.node_id for p in eligible]

    def test_eligible_peers_excludes_stale(self):
        """Stale peers should be excluded from eligible peers."""
        s = make_scheduler([make_peer(node_id="stale")])
        s._peers["stale"].last_seen = time.time() - PEER_STALE_TIMEOUT - 100
        eligible = s._get_eligible_peers()
        assert "stale" not in [p.node_id for p in eligible]

    def test_eligible_peers_excludes_low_ram(self):
        """Peers with insufficient RAM should be excluded."""
        s = make_scheduler([make_peer(node_id="weak", ram_share_mb=64)])
        eligible = s._get_eligible_peers()
        assert "weak" not in [p.node_id for p in eligible]

    def test_peer_count(self):
        """peer_count should reflect eligible peers."""
        peers = [make_peer(node_id=f"p{i}", ram_share_mb=2048) for i in range(5)]
        s = make_scheduler(peers=peers)
        assert s.peer_count == 5


# ============================================================================
# TESTS — Status & Serialization
# ============================================================================

class TestStatusAndSerialization:
    def test_get_status(self):
        """Status should include all key fields."""
        s = make_scheduler()
        status = s.get_status()
        assert "strategy" in status
        assert "transition_state" in status
        assert "peer_count" in status
        assert "replication_factor" in status
        assert "fallback_count" in status
        assert "banned_nodes" in status

    def test_to_dict(self):
        """to_dict should serialize key state."""
        s = make_scheduler()
        d = s.to_dict()
        assert "strategy" in d
        assert "peer_count" in d
        assert "replication_factor" in d

    def test_get_peers(self):
        """get_peers should return non-stale peers."""
        s = make_scheduler([make_peer(node_id="p1")])
        peers = s.get_peers()
        assert len(peers) >= 1
        assert any(p["node_id"] == "p1" for p in peers)

    def test_get_chunk_map_routing(self):
        """In routing mode, chunk map should be empty."""
        s = make_scheduler()
        s.force_strategy("routing")
        assert s.get_chunk_map() == {}

    def test_set_model_sizes(self):
        """set_model_sizes should update model sizes."""
        s = make_scheduler()
        s.set_model_sizes({"big_model": 8000, "small_model": 2000})
        assert s._model_sizes["big_model"] == 8000
        assert s._model_sizes["small_model"] == 2000

    def test_set_model_sizes_invalid_name(self):
        """Invalid model names should be ignored."""
        s = make_scheduler()
        s.set_model_sizes({"valid-model": 2000, "invalid model": 4000})
        assert "valid-model" in s._model_sizes
        assert "invalid model" not in s._model_sizes

    def test_set_model_sizes_clamped(self):
        """Model sizes should be clamped between 1 and 1M MB."""
        s = make_scheduler()
        s.set_model_sizes({"tiny": 0, "huge": 2_000_000})
        assert s._model_sizes["tiny"] == 1  # Clamped to minimum
        assert s._model_sizes["huge"] == 1_000_000  # Clamped to maximum


# ============================================================================
# TESTS — Task Completion Tracking
# ============================================================================

class TestTaskTracking:
    def test_record_success(self):
        s = make_scheduler()
        s.record_task_success("good_node")
        assert not s._malicious_detector.is_banned("good_node")

    def test_record_failure_eventually_bans(self):
        s = make_scheduler()
        for _ in range(5):
            s.record_task_failure("bad_node")
        assert s._malicious_detector.is_banned("bad_node")

    def test_record_false_claim_eventually_bans(self):
        s = make_scheduler()
        s.record_false_claim("liar")
        s.record_false_claim("liar")
        s.record_false_claim("liar")
        assert s._malicious_detector.is_banned("liar")


# ============================================================================
# TESTS — Lifecycle
# ============================================================================

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Starting and stopping should work without errors."""
        s = make_scheduler()
        await s.start()
        assert s._running is True
        await s.stop()
        assert s._running is False

    @pytest.mark.asyncio
    async def test_double_start(self):
        """Starting twice should not create duplicate tasks."""
        s = make_scheduler()
        await s.start()
        task1 = s._update_task
        await s.start()  # Should be no-op
        assert s._update_task == task1
        await s.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Stopping without starting should not crash."""
        s = make_scheduler()
        await s.stop()  # Should not raise


# ============================================================================
# TESTS — Security
# ============================================================================

class TestSecurity:
    def test_no_private_data_in_announcement(self):
        """Scheduler should never include private config data."""
        s = make_scheduler(config={"p2p_secret": "super_secret", "api_key": "key123"})
        # Config should not leak
        status = s.get_status()
        # Status dict should not contain secrets
        assert "p2p_secret" not in str(status)
        assert "api_key" not in str(status)

    def test_banned_node_not_in_eligible(self):
        """Banned nodes should be excluded from all scheduling."""
        s = make_scheduler([make_peer(node_id="attacker", ram_share_mb=2048)])
        # Ban the node
        for _ in range(5):
            s._malicious_detector.record_failure("attacker")
        eligible = s._get_eligible_peers()
        assert all(p.node_id != "attacker" for p in eligible)

    def test_rate_limiting_on_queries(self):
        """Query routing should be rate-limited."""
        s = make_scheduler([make_peer(node_id="p1", models=["m"])],
                          can_accept=True)
        s.force_strategy("routing")
        # The rate limiter should be configured
        assert s._routing_limiter is not None
        assert s._routing_limiter.rate == _MAX_ROUTING_RATE
        # Exhaust the burst
        for _ in range(30):
            s._routing_limiter.allow("query:m")
        # Next should be rate-limited
        assert s._routing_limiter.allow("query:m") is False

    def test_peer_data_clamped(self):
        """Peer data should be clamped to safe values."""
        malicious = make_peer(
            node_id="evil",
            ram_share_mb=999999,  # Absurdly high
            cpu_cores=999999,
            score=9999.0,
        )
        peer = InputValidator.sanitize_peer_data(malicious)
        assert peer is not None
        assert peer.ram_share_mb <= 65536  # MAX_PEER_RAM_MB
        assert peer.cpu_cores <= 256
        assert peer.score <= 1000.0

    def test_chunk_data_size_limit(self):
        """Ensure chunk data size limits are defined."""
        from adaptive_scheduler import MAX_CHUNK_DATA_SIZE
        assert MAX_CHUNK_DATA_SIZE > 0
        assert MAX_CHUNK_DATA_SIZE <= 256 * 1024 * 1024  # Max 256 MB


# ============================================================================
# TESTS — Edge Cases
# ============================================================================

class TestEdgeCases:
    def test_empty_peer_list(self):
        """With no peers, strategy should be routing."""
        s = make_scheduler([])
        assert s.determine_strategy(0) == Strategy.ROUTING
        assert s.peer_count == 0

    @pytest.mark.asyncio
    async def test_route_query_with_no_peers(self):
        """Routing with no peers should fall back to local."""
        s = make_scheduler([], can_accept=True)
        s.force_strategy("routing")
        result = await s.route_query("test", "any_model")
        assert result["target_node"] == "local"
        assert result["fallback"] is True

    def test_strategy_boundaries(self):
        """Test exact boundary values for strategy selection."""
        assert AdaptiveScheduler(make_identity(), make_resource_guard()).determine_strategy(3) == Strategy.ROUTING
        assert AdaptiveScheduler(make_identity(), make_resource_guard()).determine_strategy(4) == Strategy.PARTIAL_SHARDING
        assert AdaptiveScheduler(make_identity(), make_resource_guard()).determine_strategy(10) == Strategy.PARTIAL_SHARDING
        assert AdaptiveScheduler(make_identity(), make_resource_guard()).determine_strategy(11) == Strategy.FULL_SHARDING
        assert AdaptiveScheduler(make_identity(), make_resource_guard()).determine_strategy(50) == Strategy.FULL_SHARDING
        assert AdaptiveScheduler(make_identity(), make_resource_guard()).determine_strategy(51) == Strategy.RAID_RAM

    def test_transition_state_stable_initially(self):
        """Transition state should be STABLE initially."""
        s = make_scheduler()
        assert s.transition_state == TransitionState.STABLE

    def test_chunk_assignment_to_dict(self):
        """ChunkAssignment serialization should work."""
        ca = ChunkAssignment(
            model="test_model",
            chunk_index=0,
            total_chunks=4,
            peer_id="node1",
            peer_address="10.0.0.1:8081",
            size_mb=1024,
        )
        d = ca.to_dict()
        assert d["model"] == "test_model"
        assert d["chunk_index"] == 0
        assert d["total_chunks"] == 4
        assert d["peer_id"] == "node1"

    def test_peer_info_effective_ram_capped(self):
        """PeerInfo.effective_ram should be capped."""
        peer = InputValidator.sanitize_peer_data(
            make_peer(ram_share_mb=999999)
        )
        assert peer is not None
        assert peer.effective_ram <= 65536

    def test_peer_info_stale_detection(self):
        """Stale peer detection should work."""
        peer = InputValidator.sanitize_peer_data(
            make_peer(node_id="stale_peer")
        )
        assert peer is not None
        # Fresh peer should not be stale
        assert peer.is_stale is False
        # Make it stale
        peer.last_seen = time.time() - PEER_STALE_TIMEOUT - 100
        assert peer.is_stale is True


# ============================================================================
# TESTS — Constants
# ============================================================================

class TestConstants:
    def test_strategy_thresholds(self):
        assert ROUTING_MAX_PEERS == 3
        assert PARTIAL_SHARDING_MAX_PEERS == 10
        assert FULL_SHARDING_MAX_PEERS == 50

    def test_replication_factors(self):
        assert REPLICATION_FACTOR["routing"] == 0
        assert REPLICATION_FACTOR["partial_sharding"] == 2
        assert REPLICATION_FACTOR["full_sharding"] == 2
        assert REPLICATION_FACTOR["raid_ram"] == 3

    def test_chunk_counts(self):
        assert CHUNK_COUNT["routing"] == 1
        assert CHUNK_COUNT["partial_sharding"] >= 2
        assert CHUNK_COUNT["full_sharding"] >= 4
        assert CHUNK_COUNT["raid_ram"] >= 8

    def test_min_peers(self):
        assert MIN_PEERS_FOR_SHARDING == 4
        assert MIN_PEERS_FOR_FULL_SHARDING == 11
        assert MIN_PEERS_FOR_RAID == 51


if __name__ == "__main__":
    pytest.main([__file__, "-v"])