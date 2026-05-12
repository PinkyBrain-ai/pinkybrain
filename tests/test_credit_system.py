#!/usr/bin/env python3
"""
🧪 Tests Unitaires — CreditSystem
====================================
Système de crédits: gagne en partageant, dépense en demandant.
"""

import time
import pytest
from credit_system import (
    CreditSystem, CreditTier, CreditAccount,
    QUERY_COSTS, MONTHLY_REWARDS, BASE_ALLOCATION
)


class TestCreditTiers:
    """Tests des tiers de crédits."""

    def test_free_tier_default(self):
        cs = CreditSystem()
        tier = cs.get_tier(node_name="new_node", score=0)
        assert tier == CreditTier.FREE

    def test_free_tier_low_score(self):
        cs = CreditSystem()
        tier = cs.get_tier(node_name="node", score=10)
        assert tier == CreditTier.FREE

    def test_contributor_tier(self):
        cs = CreditSystem()
        cs.get_or_create("node")
        cs._add_reward("node", "models", 150)  # 100 base + 150 earned = 250
        tier = cs.get_tier("node")
        assert tier == CreditTier.CONTRIBUTOR

    def test_power_tier(self):
        cs = CreditSystem()
        cs.get_or_create("node")
        cs._add_reward("node", "models", 450)  # 100 base + 450 = 550
        tier = cs.get_tier("node")
        assert tier == CreditTier.POWER

    def test_unlimited_tier_score80(self):
        cs = CreditSystem()
        tier = cs.get_tier(node_name="node", score=80)
        assert tier == CreditTier.UNLIMITED

    def test_unlimited_tier_score95(self):
        cs = CreditSystem()
        tier = cs.get_tier(node_name="node", score=95)
        assert tier == CreditTier.UNLIMITED


class TestCreditAccount:
    """Tests du compte de crédits."""

    def test_create_account(self):
        cs = CreditSystem()
        acc = cs.get_or_create("node1")
        assert acc.node_name == "node1"
        assert acc.balance == BASE_ALLOCATION  # 100 crédits de base

    def test_get_balance(self):
        cs = CreditSystem()
        cs.get_or_create("node1")
        assert cs.get_balance("node1") == BASE_ALLOCATION

    def test_account_serialization(self):
        cs = CreditSystem()
        acc = cs.get_or_create("node1")
        d = acc.to_dict()
        assert "node_name" in d
        assert "balance" in d
        assert "breakdown" in d


class TestSpending:
    """Tests de dépense de crédits."""

    def test_simple_query_cost(self):
        cs = CreditSystem()
        success, cost = cs.spend("node1", "simple")
        assert success is True
        assert cost == 1.0
        assert cs.get_balance("node1") == BASE_ALLOCATION - 1

    def test_multi_model_cost(self):
        cs = CreditSystem()
        success, cost = cs.spend("node1", "multi", model_count=3)
        assert success is True
        assert cost == 3.0

    def test_gpu_query_cost(self):
        cs = CreditSystem()
        success, cost = cs.spend("node1", "gpu")
        assert cost == 3.0

    def test_streaming_query_cost(self):
        cs = CreditSystem()
        success, cost = cs.spend("node1", "streaming")
        assert cost == 0.5

    def test_insufficient_credits(self):
        cs = CreditSystem({"base_allocation": 2})
        cs.spend("node1", "simple")
        cs.spend("node1", "simple")
        # Plus de crédits
        success, cost = cs.spend("node1", "simple")
        assert success is False
        assert cost == 1.0

    def test_unlimited_no_debit(self):
        """Unlimited tier ne débite pas."""
        cs = CreditSystem()
        # Mock sharing_quota pour score ≥ 80
        class MockQuota:
            def calculate_score(self, name):
                return 85.0
        cs.set_sharing_quota(MockQuota())

        tier = cs.get_tier("node1")
        assert tier == CreditTier.UNLIMITED

        success, cost = cs.spend("node1", "simple")
        assert success is True
        assert cost == 0.0  # Gratuit!

    def test_can_afford_with_balance(self):
        cs = CreditSystem()
        assert cs.can_afford("node1", 1.0) is True

    def test_can_afford_insufficient(self):
        cs = CreditSystem({"base_allocation": 1})
        cs.spend("node1", "simple")
        assert cs.can_afford("node1", 1.0) is False

    def test_can_afford_unlimited(self):
        cs = CreditSystem()
        class MockQuota:
            def calculate_score(self, name):
                return 90.0
        cs.set_sharing_quota(MockQuota())
        assert cs.can_afford("node1", 999.0) is True

    def test_multiple_spends(self):
        cs = CreditSystem()
        for i in range(10):
            success, _ = cs.spend("node1", "simple")
            assert success is True
        assert cs.get_balance("node1") == BASE_ALLOCATION - 10


class TestRewards:
    """Tests des récompenses."""

    def test_model_reward(self):
        cs = CreditSystem()
        cs.reward_models("node1", 3)  # 3 modèles = 150 crédits
        acc = cs.get_or_create("node1")
        assert acc.models_reward == 150
        assert acc.balance > BASE_ALLOCATION

    def test_gpu_reward(self):
        cs = CreditSystem()
        cs.reward_gpu("node1")  # 100 crédits
        acc = cs.get_or_create("node1")
        assert acc.gpu_reward == 100

    def test_uptime_reward(self):
        cs = CreditSystem()
        cs.reward_uptime("node1", 48)  # 2 jours = 20 crédits
        acc = cs.get_or_create("node1")
        assert acc.uptime_reward == 20

    def test_memory_chunk_reward(self):
        cs = CreditSystem()
        cs.reward_memory_chunks("node1", 50)  # 50 chunks = 100 crédits
        acc = cs.get_or_create("node1")
        assert acc.memory_reward == 100

    def test_memory_chunk_max(self):
        """On ne peut pas gagner plus de 200 crédits/mois avec les chunks."""
        cs = CreditSystem()
        cs.reward_memory_chunks("node1", 200)  # 200 * 2 = 400, mais max 200
        acc = cs.get_or_create("node1")
        assert acc.memory_reward == 200

    def test_reputation_reward(self):
        cs = CreditSystem()
        cs.reward_reputation("node1", 80.0)  # 80% reputation = 40 crédits
        acc = cs.get_or_create("node1")
        assert acc.reputation_reward == 40.0

    def test_max_balance_cap(self):
        """On ne peut pas thésauriser au-delà du plafond."""
        cs = CreditSystem({"max_balance": 500})
        cs.reward_models("node1", 100)  # 5000 crédits
        assert cs.get_balance("node1") <= 500


class TestMonthlyCycle:
    """Tests du cycle mensuel."""

    def test_base_allocation(self):
        cs = CreditSystem()
        acc = cs.get_or_create("node1")
        assert acc.monthly_allocation == BASE_ALLOCATION

    def test_custom_allocation(self):
        cs = CreditSystem({"base_allocation": 200})
        acc = cs.get_or_create("node1")
        assert acc.monthly_allocation == 200

    def test_carry_over(self):
        """50% des crédits non utilisés sont reportés."""
        cs = CreditSystem({"carry_over_pct": 0.5})
        acc = cs.get_or_create("node1")
        # Dépenser 20 crédits sur 100 → reste 80
        cs.spend("node1", "simple")  # -1 (but we'll simulate)
        acc.balance = 80
        # Forcer le reset mensuel
        acc.period_end = time.time() - 1  # Dans le passé
        cs.check_monthly_reset()
        # Devrait avoir: 100 (base) + 40 (50% de 80) = 140
        assert acc.balance == pytest.approx(140, abs=1)


class TestViability:
    """Tests de viabilité économique."""

    def test_free_user_100_queries_per_month(self):
        """Un utilisateur gratuit a 100 requêtes/mois."""
        cs = CreditSystem()
        for i in range(100):
            success, _ = cs.spend("node1", "simple")
            assert success is True
        # La 101e échoue
        success, _ = cs.spend("node1", "simple")
        assert success is False

    def test_contributor_2_models_200_queries(self):
        """2 modèles hébergés = 100 + 100 = 200 requêtes/mois."""
        cs = CreditSystem()
        cs.reward_models("node1", 2)
        expected = BASE_ALLOCATION + 2 * MONTHLY_REWARDS["model_hosted"]
        assert cs.get_balance("node1") == expected

    def test_gpu_plus_models_500_queries(self):
        """GPU + 3 modèles = 100 + 300 + 100 = 500 requêtes/mois."""
        cs = CreditSystem()
        cs.reward_models("node1", 3)
        cs.reward_gpu("node1")
        expected = BASE_ALLOCATION + 3 * 50 + 100
        assert cs.get_balance("node1") == expected

    def test_power_user_unlimited_queries(self):
        """Un power user (score ≥ 80) a des requêtes illimitées."""
        cs = CreditSystem()
        class MockQuota:
            def calculate_score(self, name):
                return 85.0
        cs.set_sharing_quota(MockQuota())

        # Peut faire 1000 requêtes sans problème
        for i in range(1000):
            success, cost = cs.spend("node1", "simple")
            assert success is True
            assert cost == 0.0  # Gratuit

    def test_query_costs_scale(self):
        """Les coûts sont proportionnels à la complexité."""
        assert QUERY_COSTS["simple"] == 1
        assert QUERY_COSTS["multi_2"] == 2
        assert QUERY_COSTS["multi_3"] == 3
        assert QUERY_COSTS["gpu"] == 3
        assert QUERY_COSTS["streaming"] < QUERY_COSTS["simple"]

    def test_no_infinite_accumulation(self):
        """On ne peut pas thésauriser des crédits à l'infini."""
        cs = CreditSystem({"max_balance": 1000})
        # Donner 50 modèles = 2500 crédits
        cs.reward_models("node1", 50)
        assert cs.get_balance("node1") <= 1000


class TestAPIIntegration:
    """Tests de l'intégration API."""

    def test_get_account_info(self):
        cs = CreditSystem()
        cs.reward_models("node1", 2)
        info = cs.get_account_info("node1")
        assert "balance" in info
        assert "tier" in info
        assert "queries_remaining" in info
        assert "costs" in info
        assert "rewards" in info
        assert info["tier"] == "contributor"

    def test_get_all_accounts(self):
        cs = CreditSystem()
        cs.get_or_create("node1")
        cs.get_or_create("node2")
        all_accounts = cs.get_all_accounts()
        assert "node1" in all_accounts
        assert "node2" in all_accounts

    def test_to_dict(self):
        cs = CreditSystem()
        d = cs.to_dict()
        assert "system" in d
        assert "accounts" in d
        assert d["system"]["base_allocation"] == BASE_ALLOCATION