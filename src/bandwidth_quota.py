#!/usr/bin/env python3
"""
📡 BANDWIDTH QUOTA — PinkyBrain v5.2
======================================

Système de quota de bande passante et données mensuelles.
Comme un forfait mobile : plafond de données par mois, reset automatique.

Defaults (configurables):
- 5 GB données/mois (montant, pas %)
- 5 Mbps bande passante instantanée
- Reset le 1er de chaque mois

L'utilisateur peut monter ou baisser selon son forfait internet.
"""

import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum

logger = logging.getLogger('PinkyBrain.BandwidthQuota')


class QuotaPeriod(Enum):
    """Période de reset du quota."""
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"


@dataclass
class TransferStats:
    """Statistiques de transfert pour une période."""
    bytes_sent: int = 0
    bytes_received: int = 0
    requests_served: int = 0
    period_start: float = 0.0  # timestamp du début de période
    period_end: float = 0.0    # timestamp de fin de période

    @property
    def total_bytes(self) -> int:
        return self.bytes_sent + self.bytes_received

    @property
    def total_mb(self) -> float:
        return self.total_bytes / (1024 * 1024)

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 * 1024 * 1024)

    def to_dict(self) -> Dict:
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "total_bytes": self.total_bytes,
            "total_mb": round(self.total_mb, 1),
            "total_gb": round(self.total_gb, 2),
            "requests_served": self.requests_served,
            "period_start": self.period_start,
            "period_end": self.period_end,
        }


class BandwidthQuota:
    """Système de quota de bande passante et données par période.

    Comme un forfait mobile :
    - Plafond de données par mois (configurable)
    - Limite de débit instantané (configurable)
    - Reset automatique à chaque nouvelle période
    - L'utilisateur choisit ses limites selon son forfait internet

    Hard caps (non configurables, sécurité) :
    - Max 100 GB/mois (même avec fibre, on partage pas tout)
    - Max 100 Mbps instantané
    - Min 500 MB/mois (en dessous c'est pas utile)
    - Min 1 Mbps instantané
    """

    # ── Defaults ──────────────────────────────────────────────
    DEFAULT_MONTHLY_DATA_GB = 5.0        # 5 GB/mois par défaut
    DEFAULT_BANDWIDTH_KBPS = 5000         # 5 Mbps par défaut
    DEFAULT_PERIOD = QuotaPeriod.MONTHLY

    # ── Hard caps (non overridables) ───────────────────────────
    HARD_MIN_MONTHLY_DATA_MB = 500       # 500 MB minimum (0 = unlimited)
    HARD_MAX_MONTHLY_DATA_GB = 3072     # 3 TB max — limite actuelle, 0 = unlimited
    HARD_MIN_BANDWIDTH_KBPS = 1000       # 1 Mbps minimum
    HARD_MAX_BANDWIDTH_KBPS = 0          # 0 = no hard cap (unlimited possible for dedicated mode)

    # ── Instantané ────────────────────────────────────────────
    # Fenêtre glissante pour le débit instantané (10 secondes)
    BURST_WINDOW_SEC = 10.0

    def __init__(self, config: Dict = None):
        config = config or {}

        # ── Quota mensuel de données ──
        monthly_gb = config.get("monthly_data_gb", self.DEFAULT_MONTHLY_DATA_GB)
        # 0 = unlimited data (for dedicated mode / unlimited internet)
        if monthly_gb == 0:
            self.monthly_data_mb = 0  # unlimited, bypasses all caps
            self.monthly_data_gb = 0
        else:
            monthly_mb = monthly_gb * 1024
            # Clamp: min 500MB, max 3TB (HARD_MAX_MONTHLY_DATA_GB)
            self.monthly_data_mb = max(
                self.HARD_MIN_MONTHLY_DATA_MB,
                min(monthly_mb, self.HARD_MAX_MONTHLY_DATA_GB * 1024)
            )
            self.monthly_data_gb = round(self.monthly_data_mb / 1024, 1)

        # ── Limite bande passante instantanée ──
        bw_kbps = config.get("bandwidth_limit_kbps", self.DEFAULT_BANDWIDTH_KBPS)
        # 0 = unlimited bandwidth (for dedicated mode / unlimited internet)
        if bw_kbps == 0:
            self.bandwidth_limit_kbps = 0  # unlimited
        elif self.HARD_MAX_BANDWIDTH_KBPS == 0:
            self.bandwidth_limit_kbps = max(self.HARD_MIN_BANDWIDTH_KBPS, bw_kbps)
        else:
            self.bandwidth_limit_kbps = max(
                self.HARD_MIN_BANDWIDTH_KBPS,
                min(bw_kbps, self.HARD_MAX_BANDWIDTH_KBPS)
            )

        # ── Période de reset ──
        period_str = config.get("quota_period", "monthly")
        try:
            self.period = QuotaPeriod(period_str)
        except ValueError:
            self.period = QuotaPeriod.MONTHLY

        # ── État interne ──
        self._lock = threading.RLock()
        self._current_period: TransferStats = TransferStats()
        self._burst_bytes: list = []  # (timestamp, bytes) pour débit instantané
        self._historical: list = []    # dernieres périodes pour stats
        self._max_historical = 12      # garder 12 périodes

        # ── Init période courante ──
        self._reset_period()

        # ── Callback optionnel quand quota dépassé ──
        self._on_quota_exceeded = config.get("on_quota_exceeded", None)

        logger.info(
            f"📡 BandwidthQuota: {self.monthly_data_gb} GB/{self.period.value}, "
            f"{self.bandwidth_limit_kbps} kbps max"
        )

    # ===================================================================
    # PUBLIC API
    # ===================================================================

    def record_transfer(self, bytes_sent: int = 0, bytes_received: int = 0) -> bool:
        """Enregistrer un transfert de données.

        Returns:
            True si le transfert est accepté, False si quota dépassé.
        """
        total = bytes_sent + bytes_received
        if total == 0:
            return True

        with self._lock:
            # Vérifier quota mensuel
            if not self._check_data_quota(total):
                logger.warning(
                    f"📡 Quota mensuel dépassé: "
                    f"{self._current_period.total_mb:.0f}MB + {total/(1024*1024):.1f}MB "
                    f"> {self.monthly_data_mb}MB"
                )
                if self._on_quota_exceeded:
                    self._on_quota_exceeded("data_monthly")
                return False

            # Vérifier bande passante instantanée
            if not self._check_bandwidth(total):
                logger.debug(
                    f"📡 Bande passante limitée: débit trop élevé"
                )
                return False

            # Enregistrer
            self._current_period.bytes_sent += bytes_sent
            self._current_period.bytes_received += bytes_received
            self._current_period.requests_served += 1
            self._burst_bytes.append((time.time(), total))

            return True

    def can_transfer(self, estimated_bytes: int = 0) -> bool:
        """Vérifier si un transfert est possible sans l'enregistrer."""
        with self._lock:
            self._check_period_reset()
            return self._check_data_quota(estimated_bytes) and self._check_bandwidth(estimated_bytes)

    def get_remaining_data_mb(self) -> float:
        """Données restantes dans la période courante (MB). -1 = unlimited."""
        with self._lock:
            self._check_period_reset()
            if self.monthly_data_mb == 0:
                return -1  # unlimited
            used = self._current_period.total_bytes / (1024 * 1024)
            return max(0, self.monthly_data_mb - used)

    def get_remaining_data_pct(self) -> float:
        """Pourcentage de données restantes dans la période. -1 = unlimited."""
        with self._lock:
            self._check_period_reset()
            if self.monthly_data_mb == 0:
                return -1  # unlimited
            used_mb = self._current_period.total_bytes / (1024 * 1024)
            return max(0, min(100, (1 - used_mb / self.monthly_data_mb) * 100))

    def get_current_bandwidth_kbps(self) -> float:
        """Débit instantané actuel (kbps) sur la fenêtre glissante."""
        with self._lock:
            self._cleanup_burst_window()
            if not self._burst_bytes:
                return 0
            total_bytes = sum(b for _, b in self._burst_bytes)
            window = self.BURST_WINDOW_SEC
            bits = total_bytes * 8
            return bits / (window * 1000)  # kbps

    def update_config(self, monthly_data_gb: float = None, bandwidth_limit_kbps: int = None, period: str = None):
        """Mettre à jour la configuration du quota."""
        with self._lock:
            if monthly_data_gb is not None:
                if monthly_data_gb == 0:
                    self.monthly_data_mb = 0  # unlimited
                    self.monthly_data_gb = 0
                else:
                    mb = monthly_data_gb * 1024
                    mb = max(self.HARD_MIN_MONTHLY_DATA_MB, min(mb, self.HARD_MAX_MONTHLY_DATA_GB * 1024))
                    self.monthly_data_mb = mb
                    self.monthly_data_gb = round(mb / 1024, 1)
                logger.info(f"📡 Quota données mis à jour: {self.monthly_data_gb} GB/{self.period.value}")

            if bandwidth_limit_kbps is not None:
                if bandwidth_limit_kbps == 0:
                    self.bandwidth_limit_kbps = 0  # unlimited
                elif self.HARD_MAX_BANDWIDTH_KBPS == 0:
                    self.bandwidth_limit_kbps = max(self.HARD_MIN_BANDWIDTH_KBPS, bandwidth_limit_kbps)
                else:
                    self.bandwidth_limit_kbps = max(
                        self.HARD_MIN_BANDWIDTH_KBPS,
                        min(bandwidth_limit_kbps, self.HARD_MAX_BANDWIDTH_KBPS)
                    )
                logger.info(f"📡 Bande passante mise à jour: {self.bandwidth_limit_kbps} kbps")

            if period is not None:
                try:
                    self.period = QuotaPeriod(period)
                    logger.info(f"📡 Période mise à jour: {self.period.value}")
                except ValueError:
                    logger.warning(f"📡 Période invalide: {period}")

    def get_status(self) -> Dict:
        """Status complet du quota pour l'API et le dashboard."""
        with self._lock:
            self._check_period_reset()
            remaining_mb = self.get_remaining_data_mb()
            remaining_pct = self.get_remaining_data_pct()
            current_bw = self.get_current_bandwidth_kbps()

            return {
                # Limites configurées
                "monthly_data_gb": self.monthly_data_gb,
                "monthly_data_mb": self.monthly_data_mb,
                "bandwidth_limit_kbps": self.bandwidth_limit_kbps,
                "period": self.period.value,
                # Utilisation courante
                "used_mb": round(self._current_period.total_mb, 1),
                "used_gb": round(self._current_period.total_gb, 2),
                "remaining_mb": round(remaining_mb, 1),
                "remaining_gb": round(remaining_mb / 1024, 2),
                "remaining_pct": round(remaining_pct, 1),
                "current_bandwidth_kbps": round(current_bw, 1),
                # Détails
                "bytes_sent": self._current_period.bytes_sent,
                "bytes_received": self._current_period.bytes_received,
                "requests_served": self._current_period.requests_served,
                "period_start": self._current_period.period_start,
                "period_end": self._current_period.period_end,
                # Hard caps (info pour le UI)
                "hard_max_data_gb": self.HARD_MAX_MONTHLY_DATA_GB,  # 3 TB
                "hard_min_data_mb": self.HARD_MIN_MONTHLY_DATA_MB,
                "hard_max_bandwidth_kbps": self.HARD_MAX_BANDWIDTH_KBPS or "unlimited",
                "hard_min_bandwidth_kbps": self.HARD_MIN_BANDWIDTH_KBPS,
                # Flags illimité
                "data_unlimited": self.monthly_data_mb == 0,
                "bandwidth_unlimited": self.bandwidth_limit_kbps == 0,
                # État
                "quota_exceeded": remaining_mb != -1 and remaining_mb <= 0,
                "bandwidth_exceeded": False if self.bandwidth_limit_kbps == 0 else current_bw > self.bandwidth_limit_kbps,
            }

    def to_dict(self) -> Dict:
        return self.get_status()

    # ===================================================================
    # INTERNAL
    # ===================================================================

    def _check_data_quota(self, additional_bytes: int = 0) -> bool:
        """Vérifier si on reste dans le quota mensuel. 0 = unlimited."""
        self._check_period_reset()
        if self.monthly_data_mb == 0:
            return True  # unlimited
        total_after = self._current_period.total_bytes + additional_bytes
        limit_bytes = self.monthly_data_mb * 1024 * 1024
        return total_after <= limit_bytes

    def _check_bandwidth(self, additional_bytes: int = 0) -> bool:
        """Vérifier le débit instantané. 0 = unlimited."""
        if self.bandwidth_limit_kbps == 0:
            return True  # unlimited
        self._cleanup_burst_window()
        if not self._burst_bytes:
            return True  # Aucun trafic récent, OK

        total_bytes = sum(b for _, b in self._burst_bytes) + additional_bytes
        window = self.BURST_WINDOW_SEC
        bits = total_bytes * 8
        kbps = bits / (window * 1000)
        return kbps <= self.bandwidth_limit_kbps

    def _cleanup_burst_window(self):
        """Nettoyer les entrées vieilles de plus de BURST_WINDOW_SEC."""
        cutoff = time.time() - self.BURST_WINDOW_SEC
        self._burst_bytes = [(t, b) for t, b in self._burst_bytes if t > cutoff]

    def _check_period_reset(self):
        """Vérifier si on doit reset la période (début du mois/semaine/jour)."""
        if self._current_period.period_end == 0:
            self._reset_period()
            return

        if time.time() >= self._current_period.period_end:
            # Archiver la période
            self._historical.append(self._current_period.to_dict())
            if len(self._historical) > self._max_historical:
                self._historical = self._historical[-self._max_historical:]
            self._reset_period()

    def _reset_period(self):
        """Calculer les bornes de la nouvelle période."""
        now = time.time()
        self._current_period = TransferStats(period_start=now)

        if self.period == QuotaPeriod.MONTHLY:
            # Reset le 1er du mois suivant
            import calendar
            t = time.gmtime(now)
            if t.tm_mon == 12:
                next_year, next_mon = t.tm_year + 1, 1
            else:
                next_year, next_mon = t.tm_year, t.tm_mon + 1
            end_ts = calendar.timegm((next_year, next_mon, 1, 0, 0, 0, 0, 0, 0))
            self._current_period.period_end = end_ts

        elif self.period == QuotaPeriod.WEEKLY:
            # Reset dans 7 jours
            self._current_period.period_end = now + 7 * 86400

        elif self.period == QuotaPeriod.DAILY:
            # Reset minuit
            import calendar as cal
            t = time.gmtime(now)
            end_ts = cal.timegm((t.tm_year, t.tm_mon, t.tm_mday + 1, 0, 0, 0, 0, 0, 0))
            self._current_period.period_end = end_ts

        logger.info(
            f"📡 Nouvelle période quota: {self.period.value}, "
            f"reset dans {(self._current_period.period_end - now) / 86400:.1f} jours"
        )