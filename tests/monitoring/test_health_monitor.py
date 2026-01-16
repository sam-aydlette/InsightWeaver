"""
Tests for Health Monitor
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.monitoring.health_monitor import (
    HealthMonitor,
    get_performance_metrics,
    get_system_health,
)


class TestHealthMonitorInit:
    """Tests for HealthMonitor initialization"""

    def test_init_creates_instance(self):
        """Should create HealthMonitor instance"""
        monitor = HealthMonitor()

        assert monitor is not None


class TestGetSystemHealth:
    """Tests for get_system_health method"""

    @patch("src.monitoring.health_monitor.get_db")
    @patch("src.monitoring.health_monitor.settings")
    def test_get_system_health_returns_structure(self, mock_settings, mock_get_db):
        """Should return health structure with all metrics"""
        # Setup mocks
        mock_settings.database_url = "sqlite:///test.db"
        mock_settings.data_dir = Path("/tmp/test")
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        # Mock query results
        mock_session.query.return_value.count.return_value = 100
        mock_session.query.return_value.filter.return_value.count.return_value = 10
        mock_session.query.return_value.order_by.return_value.first.return_value = None
        mock_session.query.return_value.group_by.return_value.all.return_value = []

        with (
            patch.object(Path, "stat") as mock_stat,
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "rglob", return_value=[]),
        ):
            mock_stat.return_value.st_size = 1024 * 1024  # 1 MB
            monitor = HealthMonitor()
            result = monitor.get_system_health()

        assert "timestamp" in result
        assert "overall_status" in result
        assert "metrics" in result
        assert "issues" in result

    @patch("src.monitoring.health_monitor.get_db")
    def test_get_system_health_handles_error(self, mock_get_db):
        """Should handle database errors gracefully"""
        mock_get_db.return_value.__enter__ = MagicMock(
            side_effect=Exception("DB error")
        )

        monitor = HealthMonitor()

        result = monitor.get_system_health()

        assert result["overall_status"] == "error"
        assert len(result["issues"]) > 0


class TestCheckDatabaseHealth:
    """Tests for _check_database_health method"""

    @patch("src.monitoring.health_monitor.settings")
    def test_check_database_health(self, mock_settings):
        """Should return database health metrics"""
        mock_settings.database_url = "sqlite:///test.db"

        mock_session = MagicMock()
        mock_session.query.return_value.count.return_value = 100

        monitor = HealthMonitor()

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 1024 * 1024  # 1 MB
            with patch.object(Path, "exists", return_value=True):
                result = monitor._check_database_health(mock_session)

        assert result["status"] == "healthy"
        assert "size_mb" in result
        assert result["total_articles"] == 100


class TestCheckFeedHealth:
    """Tests for _check_feed_health method"""

    def test_check_feed_health_healthy(self):
        """Should report healthy when feeds are working"""
        mock_session = MagicMock()
        mock_session.query.return_value.count.return_value = 20
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        monitor = HealthMonitor()

        result = monitor._check_feed_health(mock_session)

        assert result["status"] == "healthy"
        assert result["total_feeds"] == 20

    def test_check_feed_health_degraded_errors(self):
        """Should report degraded when many feeds have errors"""
        mock_session = MagicMock()
        mock_session.query.return_value.count.return_value = 20
        # First filter call returns active count, subsequent calls return error/stale counts
        mock_session.query.return_value.filter.return_value.count.side_effect = [
            20,  # active_feeds
            10,  # feeds_with_errors (50% error rate > 20% threshold)
            0,  # stale_feeds
        ]

        monitor = HealthMonitor()

        result = monitor._check_feed_health(mock_session)

        assert result["status"] == "degraded"
        assert len(result["issues"]) > 0


class TestCheckSynthesisHealth:
    """Tests for _check_synthesis_health method"""

    def test_check_synthesis_health_recent(self):
        """Should report healthy with recent synthesis"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 7

        # Mock recent synthesis
        mock_synthesis = MagicMock()
        mock_synthesis.generated_at = datetime.utcnow() - timedelta(hours=2)
        mock_session.query.return_value.order_by.return_value.first.return_value = (
            mock_synthesis
        )

        monitor = HealthMonitor()

        result = monitor._check_synthesis_health(mock_session)

        assert result["status"] == "healthy"
        assert result["recent_syntheses_7d"] == 7

    def test_check_synthesis_health_stale(self):
        """Should report degraded when synthesis is stale"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 1

        # Mock old synthesis (> 48 hours)
        mock_synthesis = MagicMock()
        mock_synthesis.generated_at = datetime.utcnow() - timedelta(hours=72)
        mock_session.query.return_value.order_by.return_value.first.return_value = (
            mock_synthesis
        )

        monitor = HealthMonitor()

        result = monitor._check_synthesis_health(mock_session)

        assert result["status"] == "degraded"
        assert len(result["issues"]) > 0


class TestCheckMemoryHealth:
    """Tests for _check_memory_health method"""

    def test_check_memory_health(self):
        """Should return memory system health"""
        mock_session = MagicMock()
        mock_session.query.return_value.count.return_value = 100
        mock_session.query.return_value.filter.return_value.count.return_value = 95
        mock_session.query.return_value.group_by.return_value.all.return_value = [
            ("trend", 50),
            ("event", 30),
        ]

        monitor = HealthMonitor()

        result = monitor._check_memory_health(mock_session)

        assert result["status"] == "healthy"
        assert result["total_facts"] == 100
        assert result["active_facts"] == 95


class TestCheckRetentionStatus:
    """Tests for _check_retention_status method"""

    @patch("src.monitoring.health_monitor.settings")
    def test_check_retention_status_healthy(self, mock_settings):
        """Should report healthy with normal pending deletions"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 50

        monitor = HealthMonitor()

        result = monitor._check_retention_status(mock_session)

        assert result["status"] == "healthy"
        assert result["articles_pending_deletion"] == 50

    @patch("src.monitoring.health_monitor.settings")
    def test_check_retention_status_degraded(self, mock_settings):
        """Should report degraded with too many pending deletions"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 5000

        monitor = HealthMonitor()

        result = monitor._check_retention_status(mock_session)

        assert result["status"] == "degraded"


class TestCheckDiskSpace:
    """Tests for _check_disk_space method"""

    @patch("src.monitoring.health_monitor.settings")
    def test_check_disk_space_healthy(self, mock_settings):
        """Should report healthy with normal disk usage"""
        mock_data_dir = MagicMock()
        mock_data_dir.rglob.return_value = []
        mock_settings.data_dir = mock_data_dir

        monitor = HealthMonitor()

        result = monitor._check_disk_space()

        assert result["status"] == "healthy"
        assert result["data_dir_size_mb"] == 0


class TestDetermineOverallStatus:
    """Tests for _determine_overall_status method"""

    def test_determine_status_all_healthy(self):
        """Should return healthy when all metrics healthy"""
        monitor = HealthMonitor()

        health = {
            "metrics": {
                "database": {"status": "healthy"},
                "feeds": {"status": "healthy"},
            },
            "issues": [],
        }

        result = monitor._determine_overall_status(health)

        assert result == "healthy"

    def test_determine_status_with_degraded(self):
        """Should return degraded when any metric degraded"""
        monitor = HealthMonitor()

        health = {
            "metrics": {
                "database": {"status": "healthy"},
                "feeds": {"status": "degraded", "issues": ["Some issue"]},
            },
            "issues": [],
        }

        result = monitor._determine_overall_status(health)

        assert result == "degraded"

    def test_determine_status_with_error(self):
        """Should return error when any metric has error"""
        monitor = HealthMonitor()

        health = {
            "metrics": {
                "database": {"status": "error"},
                "feeds": {"status": "healthy"},
            },
            "issues": [],
        }

        result = monitor._determine_overall_status(health)

        assert result == "error"


class TestGetPerformanceMetrics:
    """Tests for get_performance_metrics method"""

    @patch("src.monitoring.health_monitor.get_db")
    def test_get_performance_metrics(self, mock_get_db):
        """Should return performance metrics"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        mock_session.query.return_value.filter.return_value.count.return_value = 100

        monitor = HealthMonitor()

        result = monitor.get_performance_metrics(days=7)

        assert result["period_days"] == 7
        assert "articles_collected" in result
        assert "articles_per_day" in result

    @patch("src.monitoring.health_monitor.get_db")
    def test_get_performance_metrics_handles_error(self, mock_get_db):
        """Should handle errors gracefully"""
        mock_get_db.return_value.__enter__ = MagicMock(
            side_effect=Exception("DB error")
        )

        monitor = HealthMonitor()

        result = monitor.get_performance_metrics(days=7)

        assert "error" in result


class TestConvenienceFunctions:
    """Tests for convenience functions"""

    @patch("src.monitoring.health_monitor.HealthMonitor")
    def test_get_system_health_func(self, mock_monitor_class):
        """Should call get_system_health on monitor"""
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor
        mock_monitor.get_system_health.return_value = {"overall_status": "healthy"}

        get_system_health()

        mock_monitor.get_system_health.assert_called_once()

    @patch("src.monitoring.health_monitor.HealthMonitor")
    def test_get_performance_metrics_func(self, mock_monitor_class):
        """Should call get_performance_metrics on monitor"""
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor
        mock_monitor.get_performance_metrics.return_value = {"period_days": 7}

        get_performance_metrics(days=14)

        mock_monitor.get_performance_metrics.assert_called_once_with(days=14)
