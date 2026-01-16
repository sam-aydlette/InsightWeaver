"""
Tests for Email Sender
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.newsletter.email_sender import EmailSender, NewsletterScheduler


class TestEmailSenderInit:
    """Tests for EmailSender initialization"""

    def test_init_loads_env_vars(self, monkeypatch):
        """Should load email configuration from environment"""
        monkeypatch.setenv("SMTP_SERVER", "smtp.test.com")
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        sender = EmailSender()

        assert sender.smtp_server == "smtp.test.com"
        assert sender.smtp_port == 465
        assert sender.email_username == "user@test.com"
        assert sender.email_password == "password123"
        assert sender.from_email == "sender@test.com"
        assert sender.email_enabled is True

    def test_init_default_smtp_settings(self, monkeypatch):
        """Should use default SMTP settings when not configured"""
        # Clear env vars
        for var in ["SMTP_SERVER", "SMTP_PORT", "EMAIL_USERNAME", "EMAIL_PASSWORD", "FROM_EMAIL"]:
            monkeypatch.delenv(var, raising=False)

        sender = EmailSender()

        assert sender.smtp_server == "smtp.gmail.com"
        assert sender.smtp_port == 587
        assert sender.email_enabled is False

    def test_init_disabled_without_credentials(self, monkeypatch):
        """Should disable email when credentials missing"""
        monkeypatch.delenv("EMAIL_USERNAME", raising=False)
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
        monkeypatch.delenv("FROM_EMAIL", raising=False)

        sender = EmailSender()

        assert sender.email_enabled is False


class TestSendDailyBrief:
    """Tests for sending daily brief"""

    @pytest.mark.asyncio
    async def test_send_daily_brief_success(self, sample_content_data, monkeypatch):
        """Should send daily brief successfully"""
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        sender = EmailSender()
        sender._send_email = AsyncMock(return_value=True)

        result = await sender.send_daily_brief(sample_content_data, "recipient@test.com")

        assert result is True
        sender._send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_daily_brief_saves_locally_on_failure(
        self, sample_content_data, monkeypatch, tmp_path
    ):
        """Should save locally when email fails"""
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        sender = EmailSender()
        sender._send_email = AsyncMock(return_value=False)
        sender._save_newsletter_locally = MagicMock()

        result = await sender.send_daily_brief(sample_content_data, "recipient@test.com")

        assert result is False
        sender._save_newsletter_locally.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_daily_brief_handles_exception(
        self, sample_content_data, monkeypatch
    ):
        """Should handle exceptions gracefully"""
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        sender = EmailSender()
        sender._send_email = AsyncMock(side_effect=Exception("SMTP error"))
        sender._save_newsletter_locally = MagicMock()

        result = await sender.send_daily_brief(sample_content_data, "recipient@test.com")

        assert result is False


class TestSendWeeklyTrends:
    """Tests for sending weekly trends"""

    @pytest.mark.asyncio
    async def test_send_weekly_trends_success(
        self, sample_weekly_content_data, monkeypatch
    ):
        """Should send weekly trends successfully"""
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        sender = EmailSender()
        sender._send_email = AsyncMock(return_value=True)

        result = await sender.send_weekly_trends(
            sample_weekly_content_data, "recipient@test.com"
        )

        assert result is True


class TestSendEmail:
    """Tests for low-level email sending"""

    @pytest.mark.asyncio
    async def test_send_email_returns_false_when_disabled(self, monkeypatch):
        """Should return False when email disabled"""
        monkeypatch.delenv("EMAIL_USERNAME", raising=False)

        sender = EmailSender()

        result = await sender._send_email(
            "recipient@test.com", "Subject", "<html></html>", "Text"
        )

        assert result is False

    @pytest.mark.asyncio
    @patch("src.newsletter.email_sender.smtplib.SMTP")
    async def test_send_email_success(self, mock_smtp, monkeypatch):
        """Should send email via SMTP"""
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=None)

        sender = EmailSender()

        result = await sender._send_email(
            "recipient@test.com", "Test Subject", "<html>Test</html>", "Test text"
        )

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.newsletter.email_sender.smtplib.SMTP")
    async def test_send_email_auth_error(self, mock_smtp, monkeypatch):
        """Should handle authentication error"""
        import smtplib

        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "wrong_password")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        mock_smtp.return_value.__enter__ = MagicMock(
            side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed")
        )

        sender = EmailSender()

        result = await sender._send_email(
            "recipient@test.com", "Subject", "<html></html>", "Text"
        )

        assert result is False


class TestSaveNewsletterLocally:
    """Tests for local newsletter saving"""

    def test_save_daily_newsletter(self, sample_content_data, tmp_path, monkeypatch):
        """Should save daily newsletter with correct filename"""
        # Add 'date' key for daily format
        sample_content_data["date"] = datetime.now()

        sender = EmailSender()

        # Patch Path to use tmp_path
        with patch("src.newsletter.email_sender.Path") as mock_path:
            mock_path.return_value = tmp_path / "newsletters"

            sender._save_newsletter_locally(sample_content_data, "daily", "<html>Test</html>")

    def test_save_weekly_newsletter(self, sample_weekly_content_data, monkeypatch):
        """Should save weekly newsletter with date range filename"""
        sender = EmailSender()

        with patch("src.newsletter.email_sender.Path") as mock_path:
            mock_dir = MagicMock()
            mock_path.return_value = mock_dir

            sender._save_newsletter_locally(
                sample_weekly_content_data, "weekly", "<html>Test</html>"
            )


class TestSendTestEmail:
    """Tests for test email functionality"""

    @pytest.mark.asyncio
    async def test_send_test_email_when_disabled(self, monkeypatch):
        """Should return False when email disabled"""
        monkeypatch.delenv("EMAIL_USERNAME", raising=False)

        sender = EmailSender()

        result = await sender.send_test_email("test@example.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_test_email_success(self, monkeypatch):
        """Should send test email successfully"""
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")

        sender = EmailSender()
        sender._send_email = AsyncMock(return_value=True)

        result = await sender.send_test_email("test@example.com")

        assert result is True
        sender._send_email.assert_called_once()


class TestNewsletterSchedulerInit:
    """Tests for NewsletterScheduler initialization"""

    def test_init_creates_email_sender(self):
        """Should create EmailSender if not provided"""
        scheduler = NewsletterScheduler()

        assert scheduler.email_sender is not None

    def test_init_accepts_email_sender(self, mock_email_sender):
        """Should accept provided EmailSender"""
        scheduler = NewsletterScheduler(email_sender=mock_email_sender)

        assert scheduler.email_sender is mock_email_sender

    def test_init_loads_recipient(self, monkeypatch):
        """Should load recipient from environment"""
        monkeypatch.setenv("RECIPIENT_EMAIL", "recipient@test.com")

        scheduler = NewsletterScheduler()

        assert scheduler.default_recipient == "recipient@test.com"


class TestSendDailyBriefing:
    """Tests for scheduled daily briefing"""

    @pytest.mark.asyncio
    async def test_send_daily_briefing_no_recipient(self, monkeypatch):
        """Should fail when no recipient configured"""
        monkeypatch.delenv("RECIPIENT_EMAIL", raising=False)

        scheduler = NewsletterScheduler()

        result = await scheduler.send_daily_briefing()

        assert result is False

    @pytest.mark.asyncio
    @patch("src.newsletter.content_engine.NewsletterContentEngine")
    async def test_send_daily_briefing_success(
        self, mock_engine_class, mock_email_sender, monkeypatch
    ):
        """Should send daily briefing successfully"""
        monkeypatch.setenv("RECIPIENT_EMAIL", "recipient@test.com")

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        mock_engine.generate_daily_brief_content = AsyncMock(
            return_value={"date": datetime.now(), "synthesis_data": {}}
        )

        mock_email_sender.send_daily_brief = AsyncMock(return_value=True)

        scheduler = NewsletterScheduler(email_sender=mock_email_sender)

        result = await scheduler.send_daily_briefing()

        assert result is True


class TestGetEmailStatus:
    """Tests for email status"""

    def test_get_email_status(self, monkeypatch):
        """Should return email configuration status"""
        monkeypatch.setenv("SMTP_SERVER", "smtp.test.com")
        monkeypatch.setenv("EMAIL_USERNAME", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "password123")
        monkeypatch.setenv("FROM_EMAIL", "sender@test.com")
        monkeypatch.setenv("RECIPIENT_EMAIL", "recipient@test.com")

        scheduler = NewsletterScheduler()

        status = scheduler.get_email_status()

        assert status["email_enabled"] is True
        assert status["smtp_server"] == "smtp.test.com"
        assert status["from_email"] == "sender@test.com"
        assert status["default_recipient"] == "recipient@test.com"
        assert status["credentials_configured"] is True


class TestTestEmailSystem:
    """Tests for email system testing"""

    @pytest.mark.asyncio
    async def test_test_email_system_no_recipient(self, monkeypatch):
        """Should fail when no recipient configured"""
        monkeypatch.delenv("RECIPIENT_EMAIL", raising=False)

        scheduler = NewsletterScheduler()

        result = await scheduler.test_email_system()

        assert result is False

    @pytest.mark.asyncio
    async def test_test_email_system_success(self, mock_email_sender, monkeypatch):
        """Should test email system successfully"""
        monkeypatch.setenv("RECIPIENT_EMAIL", "recipient@test.com")

        mock_email_sender.send_test_email = AsyncMock(return_value=True)

        scheduler = NewsletterScheduler(email_sender=mock_email_sender)

        result = await scheduler.test_email_system()

        assert result is True
