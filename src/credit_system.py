#!/usr/bin/env python3
"""
💰 CREDIT SYSTEM — PinkyBrain v5.2
====================================

Système de crédits pour les requêtes sur le mesh.
Comme un forfait mobile : tu gagnes des crédits en partageant,
tu dépenses en faisant des requêtes.

Principe:
- Chaque nœud gagne des crédits en partageant ses ressources
- Chaque requête coûte des crédits selon le modèle/utilisation
- Les crédits se renouvellent chaque mois (allocation de base)
- Plus tu partages, plus tu as de crédits
- Viabilité: les nœuds qui ne partagent pas ont un budget limité
- Les nœuds qui partagent beaucoup peuvent faire des requêtes illimitées

Échelle de prix (coût par requête):
- Simple query: 1 crédit
- Multi-model: 2-5 crédits (selon nombre de modèles)
- Specialty routing: 1 crédit supplémentaire
- GPU-intensive: 3 crédits
- Streaming: 0.5 crédit/requete (incitatif)

Gains par ressource partagée:
- Modèle hébergé: 50 crédits/mois par modèle
- GPU partagé: 100 crédits/mois
- Uptime (24h): 10 crédits/jour
- Données mémoire partagées: 2 crédits/chunk (max 200/mois)
- Réputation (bon voisin): 5-50 crédits/mois

Allocation de base (gratuite, même sans partager):
- 100 crédits/mois (≈ 100 requêtes simples)
- Suffisant pour essayer, pas pour abuser

Tiers:
- Free: 100 crédits/mois (base)
- Contributor: 100 + gains = 200-500
- Power: 500+ (gros contributeur)
- Unlimited: score ≥ 80 = requêtes illimitées
"""

import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from enum import Enum

logger = logging.getLogger('PinkyBrain.Credits')


class CreditTier(Enum):
    """Tiers de crédits — comme les forfaits mobile."""
    FREE = "free"           # 100 crédits/mois de base
    CONTRIBUTOR = "contributor"  # 200-500 crédits/mois
    POWER = "power"         # 500-2000 crédits/mois
    UNLIMITED = "unlimited"  # Requêtes illimitées (score ≥ 80)


# ── Coûts par type de requête ──────────────────────────────────
QUERY_COSTS = {
    "simple": 1,         # Requête simple (1 modèle)
    "multi_2": 2,       # Multi-modèle (2 modèles)
    "multi_3": 3,       # Multi-modèle (3 modèles)
    "multi_4": 4,       # Multi-modèle (4+ modèles)
    "specialty": 1,      # Routing par spécialité (surcoût)
    "gpu": 3,            # Requête GPU (coûteux)
    "streaming": 0.5,    # Streaming (incitatif, moins cher)
    "brain": 2,          # Brain LLM (plus coûteux)
}

# ── Gains mensuels par ressource ───────────────────────────────
MONTHLY_REWARDS = {
    "model_hosted": 50,      # Par modèle hébergé
    "gpu_shared": 100,      # GPU partagé
    "uptime_day": 10,        # 10 crédits/jour d'uptime
    "memory_chunk": 2,       # Par chunk mémoire partagé
    "memory_chunk_max": 200, # Max par mois
    "reputation_base": 5,    # Base de réputation
    "reputation_max": 50,    # Max par réputation
}

BASE_ALLOCATION = 100  # Crédits gratuits/mois, même sans partager


@dataclass
class CreditAccount:
    """Compte de crédits pour un nœud du mesh."""
    node_name: str
    balance: float = 0.0            # Crédits restants
    total_earned: float = 0.0       # Total gagné (tous les mois)
    total_spent: float = 0.0        # Total dépensé (tous les mois)
    monthly_allocation: float = 0.0  # Allocation ce mois-ci
    monthly_earned: float = 0.0     # Gagné ce mois-ci (rewards)
    monthly_spent: float = 0.0      # Dépensé ce mois-ci
    period_start: float = 0.0       # Début de la période
    period_end: float = 0.0          # Fin de la période
    last_reward_time: float = 0.0   # Dernière récompense
    reward_history: List[Dict] = field(default_factory=list)  # Historique récent

    # ── Sources de revenus ce mois ──
    models_reward: float = 0.0       # Gains par modèles hébergés
    gpu_reward: float = 0.0          # Gains par GPU partagé
    uptime_reward: float = 0.0       # Gains par uptime
    memory_reward: float = 0.0       # Gains par chunks mémoire
    reputation_reward: float = 0.0   # Gains par réputation

    def to_dict(self) -> dict:
        return {
            "node_name": self.node_name,
            "balance": round(self.balance, 1),
            "total_earned": round(self.total_earned, 1),
            "total_spent": round(self.total_spent, 1),
            "monthly_allocation": round(self.monthly_allocation, 1),
            "monthly_earned": round(self.monthly_earned, 1),
            "monthly_spent": round(self.monthly_spent, 1),
            "period_start": self.period_start,
            "period_end": self.period_end,
            "breakdown": {
                "models": round(self.models_reward, 1),
                "gpu": round(self.gpu_reward, 1),
                "uptime": round(self.uptime_reward, 1),
                "memory": round(self.memory_reward, 1),
                "reputation": round(self.reputation_reward, 1),
                "allocation": round(self.monthly_allocation, 1),
            },
        }


class CreditSystem:
    """Système de crédits pour le mesh PinkyBrain.

    Principe: comme un forfait mobile.
    - Chaque nœud a un compte de crédits
    - On gagne en partageant, on dépense en demandant
    - Allocation de base gratuite (100/mois)
    - Plus on partage, plus on a de crédits
    - Score ≥ 80 = illimité (gamifié, encourage le partage)

    Viabilité économique:
    - Un nœud qui ne partage rien: 100 requêtes/mois (suffit pour tester)
    - Un nœud qui partage 2 modèles: 100 + 100 = 200 requêtes/mois
    - Un nœud avec GPU + 3 modèles: 100 + 100 + 300 = 500 requêtes/mois
    - Un bon contributeur (score ≥ 80): illimité
    - Ça ne plombe pas parce que les "gros consommateurs" sont aussi
      les "gros contributeurs" — ils fournissent la capacité qu'ils consomment
    """

    def __init__(self, config: Dict = None):
        config = config or {}
        self._lock = threading.RLock()
        self._accounts: Dict[str, CreditAccount] = {}

        # Config
        self.base_allocation = config.get("base_allocation", BASE_ALLOCATION)
        self.max_balance = config.get("max_balance", 10000)  # Plafond (pas de thésaurisation infinie)
        self.carry_over_pct = config.get("carry_over_pct", 0.5)  # 50% des crédits non utilisés reportés

        # Référence au SharingQuota pour le score (set plus tard)
        self._sharing_quota = None
        self._bandwidth_quota = None

        logger.info(
            f"💰 CreditSystem: base={self.base_allocation}/mois, "
            f"max={self.max_balance}, carry_over={self.carry_over_pct*100}%"
        )

    def set_sharing_quota(self, sharing_quota):
        """Injecter la référence au SharingQuota pour les scores."""
        self._sharing_quota = sharing_quota

    def set_bandwidth_quota(self, bandwidth_quota):
        """Injecter la référence au BandwidthQuota pour le suivi data."""
        self._bandwidth_quota = bandwidth_quota

    # ===================================================================
    # COMPTE & SOLDE
    # ===================================================================

    def get_or_create(self, node_name: str) -> CreditAccount:
        """Get or create a credit account."""
        with self._lock:
            if node_name not in self._accounts:
                acc = CreditAccount(node_name=node_name)
                self._accounts[node_name] = acc
                self._allocate_monthly(acc)
            return self._accounts[node_name]

    def get_balance(self, node_name: str) -> float:
        """Solde de crédits pour un nœud."""
        acc = self.get_or_create(node_name)
        return acc.balance

    def get_tier(self, node_name: str = None, score: float = None) -> CreditTier:
        """Déterminer le tier basé sur le score ou le solde."""
        if score is None and node_name and self._sharing_quota:
            score = self._sharing_quota.calculate_score(node_name)
        elif score is None:
            score = 0

        if score >= 80:
            return CreditTier.UNLIMITED
        acc = self.get_or_create(node_name) if node_name else None
        if acc and (acc.monthly_earned + acc.monthly_allocation) >= 500:
            return CreditTier.POWER
        if acc and (acc.monthly_earned + acc.monthly_allocation) >= 200:
            return CreditTier.CONTRIBUTOR
        return CreditTier.FREE

    # ===================================================================
    # DÉPENSES (requêtes)
    # ===================================================================

    def can_afford(self, node_name: str, cost: float = 1.0) -> bool:
        """Vérifier si un nœud peut payer une requête."""
        # Unlimited tier = toujours OK
        tier = self.get_tier(node_name)
        if tier == CreditTier.UNLIMITED:
            return True

        acc = self.get_or_create(node_name)
        return acc.balance >= cost

    def spend(self, node_name: str, query_type: str = "simple", model_count: int = 1) -> Tuple[bool, float]:
        """Dépenser des crédits pour une requête.

        Returns: (success, cost)
        """
        # Calculer le coût
        cost = self._calculate_cost(query_type, model_count)

        # Unlimited tier = pas de débit
        tier = self.get_tier(node_name)
        if tier == CreditTier.UNLIMITED:
            acc = self.get_or_create(node_name)
            acc.monthly_spent += cost
            acc.total_spent += cost
            return True, 0.0  # Gratuit pour les unlimited

        acc = self.get_or_create(node_name)

        with self._lock:
            if acc.balance < cost:
                logger.warning(
                    f"💰 Crédits insuffisants pour {node_name}: "
                    f"{acc.balance:.1f} < {cost:.1f}"
                )
                return False, cost

            acc.balance -= cost
            acc.monthly_spent += cost
            acc.total_spent += cost
            return True, cost

    def _calculate_cost(self, query_type: str, model_count: int = 1) -> float:
        """Calculer le coût d'une requête."""
        if query_type == "multi":
            # Multi-modèle: coût selon le nombre de modèles
            if model_count >= 4:
                return QUERY_COSTS["multi_4"]
            return QUERY_COSTS.get(f"multi_{model_count}", QUERY_COSTS["simple"])

        cost = QUERY_COSTS.get(query_type, 1.0)
        return cost

    # ===================================================================
    # GAINS (récompenses)
    # ===================================================================

    def reward_models(self, node_name: str, model_count: int):
        """Récompenser un nœud pour les modèles hébergés."""
        reward = model_count * MONTHLY_REWARDS["model_hosted"]
        self._add_reward(node_name, "models", reward)

    def reward_gpu(self, node_name: str):
        """Récompenser un nœud pour le GPU partagé."""
        self._add_reward(node_name, "gpu", MONTHLY_REWARDS["gpu_shared"])

    def reward_uptime(self, node_name: str, hours: float = 24.0):
        """Récompenser un nœud pour l'uptime."""
        days = hours / 24.0
        reward = days * MONTHLY_REWARDS["uptime_day"]
        self._add_reward(node_name, "uptime", reward)

    def reward_memory_chunks(self, node_name: str, chunk_count: int = 1):
        """Récompenser pour les chunks mémoire partagés."""
        acc = self.get_or_create(node_name)
        current_memory = acc.memory_reward
        max_reward = MONTHLY_REWARDS["memory_chunk_max"]
        remaining = max_reward - current_memory
        if remaining <= 0:
            return  # Déjà au max
        reward = min(chunk_count * MONTHLY_REWARDS["memory_chunk"], remaining)
        self._add_reward(node_name, "memory", reward)

    def reward_reputation(self, node_name: str, reputation: float):
        """Récompenser basée sur la réputation."""
        # Scale linéaire: 50 reputation = 25 crédits, 100 = 50 crédits
        reward = (reputation / 100.0) * MONTHLY_REWARDS["reputation_max"]
        self._add_reward(node_name, "reputation", reward)

    def _add_reward(self, node_name: str, source: str, amount: float):
        """Ajouter une récompense à un compte."""
        with self._lock:
            acc = self.get_or_create(node_name)
            acc.balance = min(acc.balance + amount, self.max_balance)
            acc.monthly_earned += amount
            acc.total_earned += amount

            # Tracker la source
            if source == "models":
                acc.models_reward += amount
            elif source == "gpu":
                acc.gpu_reward += amount
            elif source == "uptime":
                acc.uptime_reward += amount
            elif source == "memory":
                acc.memory_reward += amount
            elif source == "reputation":
                acc.reputation_reward += amount

            # Historique récent (garder les 50 derniers)
            acc.reward_history.append({
                "time": time.time(),
                "source": source,
                "amount": round(amount, 1),
                "balance_after": round(acc.balance, 1),
            })
            if len(acc.reward_history) > 50:
                acc.reward_history = acc.reward_history[-50:]

    # ===================================================================
    # CYCLE MENSUEL
    # ===================================================================

    def _allocate_monthly(self, acc: CreditAccount):
        """Allouer les crédits mensuels de base."""
        import calendar
        now = time.time()
        t = time.gmtime(now)

        # Calculer la fin du mois
        if t.tm_mon == 12:
            next_year, next_mon = t.tm_year + 1, 1
        else:
            next_year, next_mon = t.tm_year, t.tm_mon + 1
        period_end = calendar.timegm((next_year, next_mon, 1, 0, 0, 0, 0, 0, 0))

        # Reporter les crédits non utilisés (carry over)
        carry_over = 0
        if acc.period_end > 0 and acc.balance > 0:
            carry_over = min(acc.balance * self.carry_over_pct, self.max_balance * 0.3)

        # Nouvelle allocation
        acc.monthly_allocation = self.base_allocation
        acc.balance = acc.monthly_allocation + carry_over
        acc.monthly_earned = 0
        acc.monthly_spent = 0
        acc.models_reward = 0
        acc.gpu_reward = 0
        acc.uptime_reward = 0
        acc.memory_reward = 0
        acc.reputation_reward = 0
        acc.period_start = now
        acc.period_end = period_end
        acc.last_reward_time = now

        logger.info(
            f"💰 Allocation mensuelle pour {acc.node_name}: "
            f"{acc.monthly_allocation} + {carry_over:.0f} carry = {acc.balance:.0f} crédits"
        )

    def check_monthly_reset(self):
        """Vérifier si on doit reset les crédits mensuels."""
        with self._lock:
            now = time.time()
            for acc in self._accounts.values():
                if acc.period_end > 0 and now >= acc.period_end:
                    self._allocate_monthly(acc)

    # ===================================================================
    # REQUÊTES DE STATUT
    # ===================================================================

    def get_account_info(self, node_name: str) -> Dict:
        """Info complète du compte pour l'API."""
        acc = self.get_or_create(node_name)
        tier = self.get_tier(node_name)
        score = 0
        if self._sharing_quota:
            score = self._sharing_quota.calculate_score(node_name)

        return {
            **acc.to_dict(),
            "tier": tier.value,
            "score": score,
            "is_unlimited": tier == CreditTier.UNLIMITED,
            "can_query": acc.balance > 0 or tier == CreditTier.UNLIMITED,
            "queries_remaining": "unlimited" if tier == CreditTier.UNLIMITED else int(acc.balance),
            "costs": QUERY_COSTS,
            "rewards": MONTHLY_REWARDS,
        }

    def get_all_accounts(self) -> Dict:
        """Tous les comptes (admin)."""
        with self._lock:
            return {name: self.get_account_info(name) for name in self._accounts}

    def to_dict(self) -> Dict:
        """Serialize pour le status endpoint."""
        with self._lock:
            return {
                "system": {
                    "base_allocation": self.base_allocation,
                    "max_balance": self.max_balance,
                    "carry_over_pct": self.carry_over_pct,
                    "accounts_count": len(self._accounts),
                },
                "accounts": {name: acc.to_dict() for name, acc in self._accounts.items()},
            }


# Fix missing import
from typing import Dict