"""
Tests for Data Retention Manager
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.maintenance.data_retention import (
    DataRetentionManager,
    cleanup_old_data,
    get_retention_status,
)


class TestDataRetentionManagerInit:
    """Tests for DataRetentionManager initialization"""

    @patch("src.maintenance.data_retention.settings")
    def test_init_loads_settings(self, mock_settings):
        """Should load retention settings on init"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        manager = DataRetentionManager()

        assert manager.retention_articles == 90
        assert manager.retention_syntheses == 180
        assert manager.retention_feed_health == 30


class TestCleanupAll:
    """Tests for cleanup_all method"""

    @patch("src.maintenance.data_retention.settings")
    @patch("src.maintenance.data_retention.get_db")
    def test_cleanup_all_dry_run(self, mock_get_db, mock_settings):
        """Should return counts without deleting in dry run mode"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        # Mock query results
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        manager = DataRetentionManager()

        result = manager.cleanup_all(dry_run=True)

        assert result["dry_run"] is True
        assert "started_at" in result
        assert "completed_at" in result
        assert "articles" in result
        assert "syntheses" in result

    @patch("src.maintenance.data_retention.settings")
    @patch("src.maintenance.data_retention.get_db")
    def test_cleanup_all_calculates_freed_space(self, mock_get_db, mock_settings):
        """Should estimate freed disk space"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        # Mock returning 100 articles and 10 syntheses
        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock() for _ in range(100)
        ]
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        manager = DataRetentionManager()

        result = manager.cleanup_all(dry_run=True)

        # Should calculate some freed space
        assert "total_freed_mb" in result


class TestCleanupOldArticles:
    """Tests for _cleanup_old_articles method"""

    @patch("src.maintenance.data_retention.settings")
    @patch("src.maintenance.data_retention.get_db")
    def test_cleanup_old_articles_none_found(self, mock_get_db, mock_settings):
        """Should handle no articles to clean up"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        manager = DataRetentionManager()

        result = manager._cleanup_old_articles(mock_session, dry_run=True)

        assert result["deleted"] == 0
        assert result["oldest_kept"] is None

    @patch("src.maintenance.data_retention.settings")
    @patch("src.maintenance.data_retention.get_db")
    def test_cleanup_old_articles_dry_run(
        self, mock_get_db, mock_settings, sample_old_article, sample_recent_article
    ):
        """Should count but not delete in dry run"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        mock_session = MagicMock()

        # Mock old articles
        mock_session.query.return_value.filter.return_value.all.return_value = [
            sample_old_article
        ]

        # Mock oldest kept article
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            sample_recent_article
        )

        manager = DataRetentionManager()

        result = manager._cleanup_old_articles(mock_session, dry_run=True)

        assert result["deleted"] == 1
        assert "cutoff_date" in result
        # Should not call delete() in dry run
        mock_session.query.return_value.filter.return_value.delete.assert_not_called()

    @patch("src.maintenance.data_retention.settings")
    def test_cleanup_old_articles_actual_delete(
        self, mock_settings, sample_old_article, sample_recent_article
    ):
        """Should delete articles when not dry run"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        mock_session = MagicMock()

        # Mock old articles
        mock_session.query.return_value.filter.return_value.all.return_value = [
            sample_old_article
        ]

        # Mock oldest kept
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            sample_recent_article
        )

        manager = DataRetentionManager()

        result = manager._cleanup_old_articles(mock_session, dry_run=False)

        assert result["deleted"] == 1
        mock_session.commit.assert_called()


class TestCleanupOldSyntheses:
    """Tests for _cleanup_old_syntheses method"""

    @patch("src.maintenance.data_retention.settings")
    def test_cleanup_old_syntheses_none_found(self, mock_settings):
        """Should handle no syntheses to clean up"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        manager = DataRetentionManager()

        result = manager._cleanup_old_syntheses(mock_session, dry_run=True)

        assert result["deleted"] == 0

    @patch("src.maintenance.data_retention.settings")
    def test_cleanup_old_syntheses_dry_run(
        self, mock_settings, sample_old_synthesis, sample_recent_synthesis
    ):
        """Should count but not delete in dry run"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        mock_session = MagicMock()

        # Mock old syntheses
        mock_session.query.return_value.filter.return_value.all.return_value = [
            sample_old_synthesis
        ]

        # Mock oldest kept
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            sample_recent_synthesis
        )

        manager = DataRetentionManager()

        result = manager._cleanup_old_syntheses(mock_session, dry_run=True)

        assert result["deleted"] == 1
        mock_session.query.return_value.filter.return_value.delete.assert_not_called()


class TestGetRetentionStatus:
    """Tests for get_retention_status method"""

    @patch("src.maintenance.data_retention.settings")
    @patch("src.maintenance.data_retention.get_db")
    def test_get_retention_status(self, mock_get_db, mock_settings):
        """Should return retention status summary"""
        mock_settings.retention_articles_days = 90
        mock_settings.retention_syntheses_days = 180
        mock_settings.retention_feed_health_days = 30

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        # Mock counts
        mock_session.query.return_value.count.return_value = 100
        mock_session.query.return_value.filter.return_value.count.return_value = 10

        # Mock oldest/newest records
        mock_article = MagicMock()
        mock_article.fetched_at = datetime.utcnow()
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_article

        manager = DataRetentionManager()

        result = manager.get_retention_status()

        assert "retention_policies" in result
        assert "current_data" in result
        assert result["retention_policies"]["articles_days"] == 90


class TestConvenienceFunctions:
    """Tests for convenience functions"""

    @patch("src.maintenance.data_retention.DataRetentionManager")
    def test_cleanup_old_data(self, mock_manager_class):
        """Should call cleanup_all on manager"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.cleanup_all.return_value = {"articles": {"deleted": 0}}

        cleanup_old_data(dry_run=True)

        mock_manager.cleanup_all.assert_called_once_with(dry_run=True)

    @patch("src.maintenance.data_retention.DataRetentionManager")
    def test_get_retention_status_func(self, mock_manager_class):
        """Should call get_retention_status on manager"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.get_retention_status.return_value = {"retention_policies": {}}

        get_retention_status()

        mock_manager.get_retention_status.assert_called_once()
