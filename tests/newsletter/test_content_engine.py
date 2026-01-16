"""
Tests for Newsletter Content Engine
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.newsletter.content_engine import NewsletterContentEngine


class TestNewsletterContentEngineInit:
    """Tests for NewsletterContentEngine initialization"""

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    @patch("src.newsletter.content_engine.ClaudeClient")
    def test_init_loads_profile(self, mock_claude, mock_curator, mock_get_profile):
        """Should load user profile on init"""
        mock_profile = MagicMock()
        mock_get_profile.return_value = mock_profile

        engine = NewsletterContentEngine()

        mock_get_profile.assert_called_once()
        assert engine.user_profile is mock_profile

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_init_handles_missing_profile(self, mock_curator, mock_get_profile):
        """Should handle missing user profile"""
        mock_get_profile.side_effect = FileNotFoundError()

        engine = NewsletterContentEngine()

        assert engine.user_profile is None

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    @patch("src.newsletter.content_engine.ClaudeClient")
    def test_init_handles_missing_api_key(
        self, mock_claude, mock_curator, mock_get_profile
    ):
        """Should handle missing API key"""
        mock_get_profile.return_value = MagicMock()
        mock_claude.side_effect = ValueError("API key not configured")

        engine = NewsletterContentEngine()

        assert engine.claude_client is None


class TestGenerateIntelligenceReport:
    """Tests for intelligence report generation"""

    @pytest.mark.asyncio
    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    @patch("src.newsletter.content_engine.get_db")
    async def test_generate_report_uses_existing_synthesis(
        self, mock_get_db, mock_curator, mock_get_profile, mock_narrative_synthesis
    ):
        """Should use existing synthesis when available"""
        mock_get_profile.return_value = MagicMock()

        # Mock database to return existing synthesis
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_narrative_synthesis
        )

        engine = NewsletterContentEngine()
        result = await engine.generate_intelligence_report(synthesis_id=123)

        assert result["synthesis_id"] == mock_narrative_synthesis.id

    @pytest.mark.asyncio
    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    @patch("src.newsletter.content_engine.get_db")
    async def test_generate_report_calculates_time_window(
        self, mock_get_db, mock_curator, mock_get_profile
    ):
        """Should calculate time window from hours parameter"""
        mock_get_profile.return_value = MagicMock()

        # Mock empty database
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
            []
        )

        engine = NewsletterContentEngine()
        result = await engine.generate_intelligence_report(hours=48)

        # Should return empty report structure
        assert result["duration_hours"] == 48
        assert result["articles_analyzed"] == 0

    @pytest.mark.asyncio
    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    @patch("src.newsletter.content_engine.get_db")
    async def test_generate_report_empty_window(
        self, mock_get_db, mock_curator, mock_get_profile
    ):
        """Should return empty report when no articles found"""
        mock_get_profile.return_value = MagicMock()

        # Mock empty database
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
            []
        )

        engine = NewsletterContentEngine()
        result = await engine.generate_intelligence_report(hours=24)

        assert result["articles_analyzed"] == 0
        assert "No articles found" in result["executive_summary"]


class TestDetermineReportType:
    """Tests for report type determination"""

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_determine_update_type(self, mock_curator, mock_get_profile):
        """Should return 'update' for short duration"""
        mock_get_profile.return_value = MagicMock()

        engine = NewsletterContentEngine()

        result = engine._determine_report_type(1)

        assert result == "update"

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_determine_daily_type(self, mock_curator, mock_get_profile):
        """Should return 'daily' for 18-30 hours"""
        mock_get_profile.return_value = MagicMock()

        engine = NewsletterContentEngine()

        assert engine._determine_report_type(24) == "daily"
        assert engine._determine_report_type(18) == "daily"
        assert engine._determine_report_type(30) == "daily"

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_determine_weekly_type(self, mock_curator, mock_get_profile):
        """Should return 'weekly' for 6-8 days"""
        mock_get_profile.return_value = MagicMock()

        engine = NewsletterContentEngine()

        assert engine._determine_report_type(168) == "weekly"  # 7 days
        assert engine._determine_report_type(144) == "weekly"  # 6 days
        assert engine._determine_report_type(192) == "weekly"  # 8 days

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_determine_custom_type(self, mock_curator, mock_get_profile):
        """Should return 'custom' for other durations"""
        mock_get_profile.return_value = MagicMock()

        engine = NewsletterContentEngine()

        assert engine._determine_report_type(48) == "custom"
        assert engine._determine_report_type(100) == "custom"


class TestFormatSynthesisReport:
    """Tests for synthesis report formatting"""

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_format_synthesis_report(
        self, mock_curator, mock_get_profile, mock_narrative_synthesis
    ):
        """Should format synthesis into report structure"""
        mock_profile = MagicMock()
        mock_profile.get_primary_location.return_value = {"city": "Fairfax"}
        mock_profile.get_professional_domains.return_value = ["cybersecurity"]
        mock_get_profile.return_value = mock_profile

        engine = NewsletterContentEngine()

        start = datetime.now() - timedelta(hours=24)
        end = datetime.now()

        result = engine._format_synthesis_report(mock_narrative_synthesis, start, end, 24)

        assert result["synthesis_id"] == mock_narrative_synthesis.id
        assert result["articles_analyzed"] == mock_narrative_synthesis.articles_analyzed
        assert "user_context" in result
        assert result["report_type"] == "daily"

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_format_synthesis_validates_data(self, mock_curator, mock_get_profile):
        """Should raise error for invalid synthesis data"""
        mock_get_profile.return_value = MagicMock()

        engine = NewsletterContentEngine()

        # Create synthesis with None data
        synthesis = MagicMock()
        synthesis.id = 1
        synthesis.synthesis_data = None

        with pytest.raises(ValueError, match="NULL synthesis_data"):
            engine._format_synthesis_report(synthesis, datetime.now(), datetime.now(), 24)

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_format_synthesis_validates_required_fields(
        self, mock_curator, mock_get_profile
    ):
        """Should raise error for missing required fields"""
        mock_get_profile.return_value = MagicMock()

        engine = NewsletterContentEngine()

        # Create synthesis with missing fields
        synthesis = MagicMock()
        synthesis.id = 1
        synthesis.synthesis_data = {"bottom_line": {}}  # Missing other required fields

        with pytest.raises(ValueError, match="missing required fields"):
            engine._format_synthesis_report(synthesis, datetime.now(), datetime.now(), 24)


class TestGenerateEmptyReport:
    """Tests for empty report generation"""

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_generate_empty_report(self, mock_curator, mock_get_profile):
        """Should generate proper empty report structure"""
        mock_profile = MagicMock()
        mock_profile.get_primary_location.return_value = {"city": "Fairfax"}
        mock_profile.get_professional_domains.return_value = []
        mock_get_profile.return_value = mock_profile

        engine = NewsletterContentEngine()

        start = datetime.now() - timedelta(hours=24)
        end = datetime.now()

        result = engine._generate_empty_report(start, end, 24)

        assert result["articles_analyzed"] == 0
        assert "No articles found" in result["executive_summary"]
        assert result["synthesis_data"] == {}
        assert result["report_type"] == "daily"

    @patch("src.newsletter.content_engine.get_user_profile")
    @patch("src.newsletter.content_engine.ContextCurator")
    def test_generate_empty_report_no_profile(self, mock_curator, mock_get_profile):
        """Should handle missing user profile in empty report"""
        mock_get_profile.side_effect = FileNotFoundError()

        engine = NewsletterContentEngine()

        start = datetime.now() - timedelta(hours=24)
        end = datetime.now()

        result = engine._generate_empty_report(start, end, 24)

        assert result["user_context"] == {}
