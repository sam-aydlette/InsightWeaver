"""
Tests for Newsletter System
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.newsletter.newsletter_system import NewsletterSystem


class TestNewsletterSystemInit:
    """Tests for NewsletterSystem initialization"""

    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    def test_init_creates_components(self, mock_scheduler, mock_engine):
        """Should create content engine and scheduler"""
        system = NewsletterSystem()

        mock_engine.assert_called_once()
        mock_scheduler.assert_called_once()
        assert system.content_engine is not None
        assert system.scheduler is not None


class TestGenerateReport:
    """Tests for report generation"""

    @pytest.mark.asyncio
    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.DailyBriefTemplate")
    async def test_generate_report_success(
        self, mock_template, mock_scheduler, mock_engine, sample_content_data
    ):
        """Should generate report successfully"""
        # Setup mocks
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.generate_intelligence_report = AsyncMock(
            return_value=sample_content_data
        )
        mock_template.generate_html.return_value = "<html>Test</html>"

        system = NewsletterSystem()

        result = await system.generate_report(hours=24, save_local=False, send_email=False)

        assert result["success"] is True
        assert result["articles_analyzed"] == 10

    @pytest.mark.asyncio
    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.DailyBriefTemplate")
    @patch("src.newsletter.newsletter_system.settings")
    async def test_generate_report_saves_locally(
        self, mock_settings, mock_template, mock_scheduler, mock_engine, sample_content_data, tmp_path
    ):
        """Should save report locally when requested"""
        # Setup mocks
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.generate_intelligence_report = AsyncMock(
            return_value=sample_content_data
        )
        mock_template.generate_html.return_value = "<html>Test</html>"
        mock_settings.briefings_dir = tmp_path

        system = NewsletterSystem()

        result = await system.generate_report(hours=24, save_local=True, send_email=False)

        assert result["local_saved"] is True
        assert "local_path" in result

    @pytest.mark.asyncio
    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    async def test_generate_report_trust_verification_failed(
        self, mock_scheduler, mock_engine, sample_content_data
    ):
        """Should skip HTML generation when trust verification fails"""
        # Setup content data with failed trust verification
        sample_content_data["trust_verification"] = {"passed": False, "issues": ["Issue 1"]}

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.generate_intelligence_report = AsyncMock(
            return_value=sample_content_data
        )

        system = NewsletterSystem()

        result = await system.generate_report(hours=24, save_local=True)

        assert result["success"] is False
        assert result.get("trust_verification_failed") is True

    @pytest.mark.asyncio
    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.DailyBriefTemplate")
    async def test_generate_report_handles_exception(
        self, mock_template, mock_scheduler, mock_engine, sample_content_data
    ):
        """Should handle exceptions gracefully"""
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.generate_intelligence_report = AsyncMock(
            return_value=sample_content_data
        )
        mock_template.generate_html.side_effect = Exception("Template error")

        system = NewsletterSystem()

        result = await system.generate_report(hours=24, save_local=False)

        assert result["success"] is False
        assert "error" in result


class TestSaveReportLocal:
    """Tests for local report saving"""

    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.settings")
    def test_save_report_creates_file(
        self, mock_settings, mock_scheduler, mock_engine, sample_content_data, tmp_path
    ):
        """Should create HTML file with correct naming"""
        mock_settings.briefings_dir = tmp_path

        system = NewsletterSystem()

        filepath = system._save_report_local(sample_content_data, "<html>Test</html>")

        assert filepath.exists()
        assert "intel_report_daily" in filepath.name
        assert filepath.suffix == ".html"

    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.settings")
    def test_save_report_creates_directory(
        self, mock_settings, mock_scheduler, mock_engine, sample_content_data, tmp_path
    ):
        """Should create briefings directory if not exists"""
        briefings_dir = tmp_path / "new_dir" / "briefings"
        mock_settings.briefings_dir = briefings_dir

        system = NewsletterSystem()

        filepath = system._save_report_local(sample_content_data, "<html>Test</html>")

        assert briefings_dir.exists()
        assert filepath.exists()


class TestSaveJsonReport:
    """Tests for JSON report saving"""

    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.settings")
    def test_save_json_report(
        self, mock_settings, mock_scheduler, mock_engine, sample_content_data, tmp_path
    ):
        """Should save JSON report correctly"""
        mock_settings.briefings_dir = tmp_path

        system = NewsletterSystem()

        filepath = system.save_json_report(sample_content_data)

        assert filepath.exists()
        assert filepath.suffix == ".json"

        # Verify content
        import json

        with open(filepath) as f:
            data = json.load(f)
            assert data["type"] == "intelligence_brief"
            assert "time_window" in data


class TestPreviewReport:
    """Tests for report preview"""

    @pytest.mark.asyncio
    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.DailyBriefTemplate")
    async def test_preview_report(
        self, mock_template, mock_scheduler, mock_engine, sample_content_data
    ):
        """Should return HTML content for preview"""
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.generate_intelligence_report = AsyncMock(
            return_value=sample_content_data
        )
        mock_template.generate_html.return_value = "<html>Preview</html>"

        system = NewsletterSystem()

        result = await system.preview_report(hours=24)

        assert result == "<html>Preview</html>"


class TestGetSystemStatus:
    """Tests for system status"""

    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.settings")
    def test_get_system_status(self, mock_settings, mock_scheduler_class, mock_engine):
        """Should return system status"""
        mock_settings.briefings_dir = Path("/tmp/briefings")

        mock_scheduler_instance = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler_instance
        mock_scheduler_instance.get_email_status.return_value = {
            "email_enabled": True,
            "credentials_configured": True,
            "smtp_server": "smtp.gmail.com",
            "default_recipient": "test@example.com",
        }

        system = NewsletterSystem()

        status = system.get_system_status()

        assert "system_version" in status
        assert "content_engine" in status
        assert "email_system" in status
        assert "capabilities" in status


class TestTestSystem:
    """Tests for system testing functionality"""

    @pytest.mark.asyncio
    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    @patch("src.newsletter.newsletter_system.DailyBriefTemplate")
    async def test_test_system_all_pass(
        self, mock_template, mock_scheduler_class, mock_engine
    ):
        """Should return success when all tests pass"""
        # Setup mocks
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.generate_intelligence_report = AsyncMock(
            return_value={
                "executive_summary": "Test summary",
                "synthesis_data": {},
            }
        )

        mock_template.generate_html.return_value = "<html>" + "x" * 2000 + "</html>"

        mock_scheduler_instance = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler_instance
        mock_scheduler_instance.get_email_status.return_value = {
            "email_enabled": True,
            "credentials_configured": True,
        }
        mock_scheduler_instance.test_email_system = AsyncMock(return_value=True)

        system = NewsletterSystem()

        results = await system.test_system()

        assert results["content_engine"] is True
        assert results["template_rendering"] is True

    @pytest.mark.asyncio
    @patch("src.newsletter.newsletter_system.NewsletterContentEngine")
    @patch("src.newsletter.newsletter_system.NewsletterScheduler")
    async def test_test_system_handles_errors(self, mock_scheduler, mock_engine):
        """Should handle errors during testing"""
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance
        mock_engine_instance.generate_intelligence_report = AsyncMock(
            side_effect=Exception("Test error")
        )

        system = NewsletterSystem()

        results = await system.test_system()

        assert results["overall_status"] == "FAILED"
        assert "error" in results
