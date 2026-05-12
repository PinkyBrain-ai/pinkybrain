#!/usr/bin/env python3
"""
🧪 Tests Unitaires — BandwidthQuota
=====================================
Quota mensuel de données et bande passante, comme un forfait mobile.
"""

import time
import pytest
from bandwidth_quota import BandwidthQuota, QuotaPeriod, TransferStats


class TestInitialization:
    """Tests d'initialisation et configuration."""

    def test_default_config(self):
        bq = BandwidthQuota()
        assert bq.monthly_data_gb == 5.0
        assert bq.bandwidth_limit_kbps == 5000
        assert bq.period == QuotaPeriod.MONTHLY

    def test_custom_config(self):
        bq = BandwidthQuota({
            "monthly_data_gb": 10.0,
            "bandwidth_limit_kbps": 10000,
            "quota_period": "weekly",
        })
        assert bq.monthly_data_gb == 10.0
        assert bq.bandwidth_limit_kbps == 10000
        assert bq.period == QuotaPeriod.WEEKLY

    def test_data_quota_clamped_min(self):
        """En dessous de 500MB, clampé à 500MB."""
        bq = BandwidthQuota({"monthly_data_gb": 0.1})  # 100MB
        assert bq.monthly_data_mb == 500  # clamped to min

    def test_data_quota_clamped_max(self):
        """Hard max is 0 (unlimited), so 500GB is accepted as-is."""
        bq = BandwidthQuota({"monthly_data_gb": 500})
        assert bq.monthly_data_gb == 500.0  # under 3TB cap, accepted

    def test_bandwidth_clamped_min(self):
        """En dessous de 1 Mbps, clampé à 1 Mbps."""
        bq = BandwidthQuota({"bandwidth_limit_kbps": 100})  # 100 kbps
        assert bq.bandwidth_limit_kbps == 1000  # min

    def test_bandwidth_clamped_max(self):
        """Hard max is 0 (unlimited), so 500Mbps is accepted."""
        bq = BandwidthQuota({"bandwidth_limit_kbps": 500000})
        assert bq.bandwidth_limit_kbps == 500000  # no hard cap, accepted


class TestTransferRecording:
    """Tests d'enregistrement des transferts."""

    def test_record_small_transfer(self):
        bq = BandwidthQuota()
        assert bq.record_transfer(bytes_sent=1024) is True
        status = bq.get_status()
        assert status["bytes_sent"] == 1024
        assert status["requests_served"] == 1

    def test_record_send_and_receive(self):
        bq = BandwidthQuota({"monthly_data_gb": 1.0})  # 1GB quota
        bq.record_transfer(bytes_sent=5000, bytes_received=3000)
        status = bq.get_status()
        assert status["bytes_sent"] == 5000
        assert status["bytes_received"] == 3000

    def test_zero_transfer_always_accepted(self):
        bq = BandwidthQuota()
        assert bq.record_transfer(0, 0) is True

    def test_can_transfer_check(self):
        bq = BandwidthQuota()
        # 5GB = ~5120MB, on peut transférer 1MB
        assert bq.can_transfer(1024 * 1024) is True

    def test_can_transfer_exceeds_quota(self):
        bq = BandwidthQuota({"monthly_data_gb": 0.001})  # ~1MB min will clamp
        # Monthly data clamped to 500MB min
        assert bq.can_transfer(1024) is True


class TestMonthlyQuota:
    """Tests du quota mensuel."""

    def test_quota_not_exceeded_initially(self):
        bq = BandwidthQuota()
        assert bq.get_remaining_data_pct() == 100.0

    def test_quota_decreases_with_usage(self):
        bq = BandwidthQuota({"monthly_data_gb": 1.0})  # 1GB
        # Transférer 100MB
        bq.record_transfer(bytes_sent=100 * 1024 * 1024)
        remaining = bq.get_remaining_data_pct()
        assert 85 < remaining < 95  # ~90% restant

    def test_quota_exceeded_blocks_transfer(self):
        """Quand le quota est dépassé, les transferts sont bloqués."""
        bq = BandwidthQuota({"monthly_data_gb": 0.001})  # sera clampé à 500MB
        # 500MB min, on envoie 500MB
        bq.record_transfer(bytes_sent=500 * 1024 * 1024)
        # Le prochain transfert devrait être bloqué
        assert bq.record_transfer(bytes_sent=1024) is False

    def test_remaining_data_mb(self):
        bq = BandwidthQuota({"monthly_data_gb": 1.0})  # 1024MB
        bq.record_transfer(bytes_sent=100 * 1024 * 1024)  # 100MB
        remaining = bq.get_remaining_data_mb()
        assert 900 < remaining < 950  # ~924MB restant

    def test_remaining_data_pct_never_negative(self):
        bq = BandwidthQuota({"monthly_data_gb": 1.0})
        # Simulate exceeding quota by directly setting bytes
        bq._current_period.bytes_sent = 2 * 1024 * 1024 * 1024  # 2GB
        assert bq.get_remaining_data_pct() == 0.0


class TestBandwidthLimit:
    """Tests de la limite de bande passante instantanée."""

    def test_bandwidth_starts_at_zero(self):
        bq = BandwidthQuota()
        assert bq.get_current_bandwidth_kbps() == 0

    def test_bandwidth_increases_with_transfer(self):
        bq = BandwidthQuota()
        bq.record_transfer(bytes_sent=100000)  # 100KB
        bw = bq.get_current_bandwidth_kbps()
        assert bw > 0

    def test_bandwidth_limit_blocks_excess(self):
        """Quand le débit instantané dépasse la limite, bloquer."""
        bq = BandwidthQuota({"bandwidth_limit_kbps": 100})  # 100 kbps = 12.5 KB/s
        # Remplir la fenêtre avec beaucoup de données
        for _ in range(100):
            bq._burst_bytes.append((time.time(), 50000))  # 5MB total in 10s window
        # Le débit moyen = 5MB * 8 / 10s = 4Mbps = 4000kbps >> 100kbps
        assert bq.can_transfer(1) is False


class TestConfigUpdate:
    """Tests de mise à jour dynamique de la config."""

    def test_update_data_quota(self):
        bq = BandwidthQuota()
        bq.update_config(monthly_data_gb=20.0)
        assert bq.monthly_data_gb == 20.0

    def test_update_bandwidth(self):
        bq = BandwidthQuota()
        bq.update_config(bandwidth_limit_kbps=20000)
        assert bq.bandwidth_limit_kbps == 20000

    def test_update_period(self):
        bq = BandwidthQuota()
        bq.update_config(period="daily")
        assert bq.period == QuotaPeriod.DAILY

    def test_update_clamps_data_min(self):
        bq = BandwidthQuota()
        bq.update_config(monthly_data_gb=0.01)  # Trop bas
        assert bq.monthly_data_mb == 500  # Clampé au min

    def test_update_clamps_data_max(self):
        bq = BandwidthQuota()
        bq.update_config(monthly_data_gb=999)
        assert bq.monthly_data_gb == 999.0  # under 3TB cap, accepted

    def test_update_clamps_bandwidth_min(self):
        bq = BandwidthQuota()
        bq.update_config(bandwidth_limit_kbps=50)
        assert bq.bandwidth_limit_kbps == 1000  # Min 1 Mbps

    def test_update_clamps_bandwidth_max(self):
        bq = BandwidthQuota()
        bq.update_config(bandwidth_limit_kbps=999999)
        assert bq.bandwidth_limit_kbps == 999999  # no hard cap, accepted

    def test_invalid_period_ignored(self):
        bq = BandwidthQuota()
        bq.update_config(period="invalid")
        assert bq.period == QuotaPeriod.MONTHLY  # unchanged


class TestGetStatus:
    """Tests du rapport de status."""

    def test_status_complete(self):
        bq = BandwidthQuota()
        bq.record_transfer(bytes_sent=1024 * 1024)  # 1MB
        status = bq.get_status()

        # Vérifier que toutes les clés sont présentes
        assert "monthly_data_gb" in status
        assert "monthly_data_mb" in status
        assert "bandwidth_limit_kbps" in status
        assert "period" in status
        assert "used_mb" in status
        assert "used_gb" in status
        assert "remaining_mb" in status
        assert "remaining_gb" in status
        assert "remaining_pct" in status
        assert "current_bandwidth_kbps" in status
        assert "bytes_sent" in status
        assert "bytes_received" in status
        assert "requests_served" in status
        assert "quota_exceeded" in status
        assert "hard_max_data_gb" in status
        assert "hard_min_data_mb" in status
        assert "hard_max_bandwidth_kbps" in status
        assert "hard_min_bandwidth_kbps" in status

    def test_status_shows_usage(self):
        bq = BandwidthQuota({"monthly_data_gb": 1.0})
        bq.record_transfer(bytes_sent=100 * 1024 * 1024)  # 100MB
        status = bq.get_status()
        assert status["used_mb"] > 90
        assert status["remaining_pct"] > 80
        assert status["quota_exceeded"] is False

    def test_status_quotas_exceeded(self):
        bq = BandwidthQuota({"monthly_data_gb": 0.001})  # clampé à 500MB
        bq.record_transfer(bytes_sent=500 * 1024 * 1024)  # 500MB
        status = bq.get_status()
        assert status["quota_exceeded"] is True


class TestPeriodReset:
    """Tests du reset de période."""

    def test_period_start_set(self):
        bq = BandwidthQuota()
        assert bq._current_period.period_start > 0
        assert bq._current_period.period_end > bq._current_period.period_start

    def test_period_end_future(self):
        bq = BandwidthQuota()
        assert bq._current_period.period_end > time.time()

    def test_weekly_period(self):
        bq = BandwidthQuota({"quota_period": "weekly"})
        # Reset dans ~7 jours
        duration_days = (bq._current_period.period_end - time.time()) / 86400
        assert 6 < duration_days < 8

    def test_daily_period(self):
        bq = BandwidthQuota({"quota_period": "daily"})
        duration_days = (bq._current_period.period_end - time.time()) / 86400
        assert 0 < duration_days < 1.5


class TestHardCaps:
    """Tests des hard caps de sécurité."""

    def test_hard_max_data(self):
        assert BandwidthQuota.HARD_MAX_MONTHLY_DATA_GB == 3072  # 3 TB max

    def test_hard_min_data(self):
        assert BandwidthQuota.HARD_MIN_MONTHLY_DATA_MB == 500

    def test_hard_max_bandwidth(self):
        assert BandwidthQuota.HARD_MAX_BANDWIDTH_KBPS == 0  # 0 = unlimited

    def test_hard_min_bandwidth(self):
        assert BandwidthQuota.HARD_MIN_BANDWIDTH_KBPS == 1000

    def test_cannot_override_data_max(self):
        bq = BandwidthQuota({"monthly_data_gb": 999})
        assert bq.monthly_data_gb == 999.0  # under 3TB cap

    def test_data_3tb_hard_cap(self):
        """Over 3TB should be clamped to 3TB."""
        bq = BandwidthQuota({"monthly_data_gb": 5000})
        assert bq.monthly_data_gb == 3072.0  # clamped to 3TB

    def test_data_exactly_3tb(self):
        """3TB should be accepted."""
        bq = BandwidthQuota({"monthly_data_gb": 3072})
        assert bq.monthly_data_gb == 3072.0

    def test_cannot_override_bandwidth_max(self):
        bq = BandwidthQuota({"bandwidth_limit_kbps": 999999})
        assert bq.bandwidth_limit_kbps == 999999  # no hard cap


class TestTransferStats:
    """Tests de la classe TransferStats."""

    def test_total_bytes(self):
        ts = TransferStats(bytes_sent=1000, bytes_received=500)
        assert ts.total_bytes == 1500

    def test_total_mb(self):
        ts = TransferStats(bytes_sent=1024*1024, bytes_received=0)
        assert abs(ts.total_mb - 1.0) < 0.1

    def test_total_gb(self):
        ts = TransferStats(bytes_sent=1024*1024*1024, bytes_received=0)
        assert abs(ts.total_gb - 1.0) < 0.01

    def test_to_dict(self):
        ts = TransferStats(bytes_sent=100, bytes_received=200)
        d = ts.to_dict()
        assert d["bytes_sent"] == 100
        assert d["bytes_received"] == 200
        assert d["total_bytes"] == 300

class TestUnlimitedDedicatedMode:
    """Tests pour le mode dédié (fous-fous) — 0 = unlimited."""

    def test_unlimited_data(self):
        """0 = unlimited data."""
        bq = BandwidthQuota({"monthly_data_gb": 0})
        assert bq.monthly_data_gb == 0
        assert bq.monthly_data_mb == 0
        assert bq.can_transfer(10 * 1024 * 1024 * 1024)  # 10GB ok

    def test_unlimited_bandwidth(self):
        """0 = unlimited bandwidth."""
        bq = BandwidthQuota({"bandwidth_limit_kbps": 0})
        assert bq.bandwidth_limit_kbps == 0
        # Burst doesn't block
        for _ in range(100):
            bq._burst_bytes.append((time.time(), 50000))
        assert bq.can_transfer(1) is True

    def test_full_dedicated_mode(self):
        """Both unlimited = full dedicated mode."""
        bq = BandwidthQuota({"monthly_data_gb": 0, "bandwidth_limit_kbps": 0})
        assert bq.monthly_data_mb == 0
        assert bq.bandwidth_limit_kbps == 0
        bq.record_transfer(bytes_sent=50 * 1024 * 1024 * 1024)  # 50GB
        assert bq.can_transfer(1024) is True
        status = bq.get_status()
        assert status["data_unlimited"] is True
        assert status["bandwidth_unlimited"] is True
        assert status["quota_exceeded"] is False

    def test_update_to_unlimited(self):
        """Switch from normal to unlimited via update_config."""
        bq = BandwidthQuota()
        assert bq.monthly_data_gb == 5.0
        bq.update_config(monthly_data_gb=0, bandwidth_limit_kbps=0)
        assert bq.monthly_data_gb == 0
        assert bq.bandwidth_limit_kbps == 0

    def test_update_from_unlimited_to_normal(self):
        """Switch from unlimited back to normal."""
        bq = BandwidthQuota({"monthly_data_gb": 0, "bandwidth_limit_kbps": 0})
        bq.update_config(monthly_data_gb=10, bandwidth_limit_kbps=10000)
        assert bq.monthly_data_gb == 10.0
        assert bq.bandwidth_limit_kbps == 10000

    def test_remaining_minus_one_means_unlimited(self):
        """get_remaining_data_mb returns -1 for unlimited."""
        bq = BandwidthQuota({"monthly_data_gb": 0})
        assert bq.get_remaining_data_mb() == -1

    def test_remaining_pct_minus_one_means_unlimited(self):
        """get_remaining_data_pct returns -1 for unlimited."""
        bq = BandwidthQuota({"monthly_data_gb": 0})
        assert bq.get_remaining_data_pct() == -1
