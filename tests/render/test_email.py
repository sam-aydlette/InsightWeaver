"""
Tests for EmailRenderer against a fixture BriefDocument.

Delivery is exercised through a stub SMTP transport: the tests assert which
smtplib calls are made, in what order, with which settings. No message is sent
and no credential is read from a real environment.
"""

import re

import pytest

from src.render.email import EmailDeliveryError, EmailRenderer, SMTPConfig
from src.render.html import HTMLRenderer

ENV_VARS = (
    "SMTP_SERVER",
    "SMTP_PORT",
    "EMAIL_USERNAME",
    "EMAIL_PASSWORD",
    "FROM_EMAIL",
    "RECIPIENT_EMAIL",
)


@pytest.fixture
def smtp_env(monkeypatch):
    """The SMTP variables the project already documents in .env."""
    values = {
        "SMTP_SERVER": "smtp.example.test",
        "SMTP_PORT": "587",
        "EMAIL_USERNAME": "sender@example.test",
        "EMAIL_PASSWORD": "not-a-real-password",
        "FROM_EMAIL": "sender@example.test",
        "RECIPIENT_EMAIL": "reader@example.test",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


@pytest.fixture
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class StubSMTP:
    """Records the calls a real smtplib.SMTP would receive."""

    instances: list["StubSMTP"] = []

    def __init__(self, server, port, timeout=None):
        self.server = server
        self.port = port
        self.timeout = timeout
        self.calls: list[str] = []
        self.messages: list = []
        StubSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("close")
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, username, password):
        self.calls.append("login")
        self.username = username
        self.password = password

    def send_message(self, message):
        self.calls.append("send_message")
        self.messages.append(message)


@pytest.fixture
def stub_smtp(monkeypatch):
    StubSMTP.instances = []
    monkeypatch.setattr("smtplib.SMTP", StubSMTP)
    monkeypatch.setattr("smtplib.SMTP_SSL", StubSMTP)
    return StubSMTP


class TestSMTPConfig:
    def test_reads_the_documented_variables(self, smtp_env):
        cfg = SMTPConfig.from_env()
        assert cfg.server == "smtp.example.test"
        assert cfg.port == 587
        assert cfg.username == "sender@example.test"
        assert cfg.from_email == "sender@example.test"
        assert cfg.recipient == "reader@example.test"

    def test_explicit_recipient_overrides_the_env_default(self, smtp_env):
        assert SMTPConfig.from_env("other@example.test").recipient == "other@example.test"

    def test_port_defaults_to_587(self, smtp_env, monkeypatch):
        monkeypatch.delenv("SMTP_PORT")
        assert SMTPConfig.from_env().port == 587

    def test_names_every_missing_variable(self, clean_env):
        with pytest.raises(EmailDeliveryError) as excinfo:
            SMTPConfig.from_env()
        message = str(excinfo.value)
        for name in ("SMTP_SERVER", "EMAIL_USERNAME", "EMAIL_PASSWORD", "FROM_EMAIL"):
            assert name in message
        assert "RECIPIENT_EMAIL" in message

    def test_never_echoes_the_password(self, smtp_env, monkeypatch):
        monkeypatch.delenv("SMTP_SERVER")
        with pytest.raises(EmailDeliveryError) as excinfo:
            SMTPConfig.from_env()
        assert smtp_env["EMAIL_PASSWORD"] not in str(excinfo.value)

    def test_rejects_a_non_numeric_port(self, smtp_env, monkeypatch):
        monkeypatch.setenv("SMTP_PORT", "not-a-port")
        with pytest.raises(EmailDeliveryError, match="SMTP_PORT"):
            SMTPConfig.from_env()


class TestRender:
    def test_subject_is_stable_and_derived_from_the_document(self, brief_document):
        renderer = EmailRenderer()
        assert renderer.subject(brief_document) == "Intelligence Brief — 2026-05-15 (2 situations)"
        assert renderer.subject(brief_document) == renderer.subject(brief_document)

    def test_subject_singular_situation(self, hostile_document):
        assert EmailRenderer().subject(hostile_document).endswith("(1 situation)")

    def test_message_is_multipart_alternative(self, brief_document):
        message = EmailRenderer().render(
            brief_document, from_email="a@example.test", recipient="b@example.test"
        )
        assert message["From"] == "a@example.test"
        assert message["To"] == "b@example.test"
        types = {part.get_content_type() for part in message.walk() if not part.is_multipart()}
        assert types == {"text/plain", "text/html"}

    def test_html_part_is_the_html_renderer_output(self, brief_document):
        message = EmailRenderer().render(brief_document)
        html_part = message.get_body(preferencelist=("html"))
        assert html_part.get_content() == HTMLRenderer().render(brief_document)

    def test_text_part_carries_no_ansi_escapes(self, brief_document):
        text = EmailRenderer().render_text(brief_document)
        assert not re.search(r"\x1b\[", text)
        assert "INTELLIGENCE BRIEF" in text

    def test_is_deterministic(self, brief_document):
        renderer = EmailRenderer()
        first = renderer.render(brief_document).as_bytes()
        second = renderer.render(brief_document).as_bytes()
        # Boundaries are random per message, so compare the payloads.
        assert renderer.render_text(brief_document) == renderer.render_text(brief_document)
        assert len(first) == len(second)


class TestSend:
    def test_uses_starttls_then_login_then_send(self, brief_document, smtp_env, stub_smtp):
        recipient = EmailRenderer().send(brief_document)
        assert recipient == "reader@example.test"
        smtp = stub_smtp.instances[0]
        assert smtp.server == "smtp.example.test"
        assert smtp.port == 587
        assert smtp.calls == ["starttls", "login", "send_message", "close"]
        assert smtp.username == "sender@example.test"
        assert smtp.messages[0]["To"] == "reader@example.test"

    def test_port_465_uses_implicit_tls_without_starttls(
        self, brief_document, smtp_env, stub_smtp, monkeypatch
    ):
        monkeypatch.setenv("SMTP_PORT", "465")
        EmailRenderer().send(brief_document)
        assert stub_smtp.instances[0].calls == ["login", "send_message", "close"]

    def test_explicit_recipient(self, brief_document, smtp_env, stub_smtp):
        assert EmailRenderer().send(brief_document, recipient="x@example.test") == "x@example.test"

    def test_transport_failure_raises_without_retrying(self, brief_document, smtp_env, monkeypatch):
        attempts = []

        def explode(*args, **kwargs):
            attempts.append(args)
            raise OSError("connection refused")

        monkeypatch.setattr("smtplib.SMTP", explode)
        with pytest.raises(EmailDeliveryError, match="failed"):
            EmailRenderer().send(brief_document)
        assert len(attempts) == 1

    def test_missing_configuration_raises_before_connecting(
        self, brief_document, clean_env, stub_smtp
    ):
        with pytest.raises(EmailDeliveryError):
            EmailRenderer().send(brief_document)
        assert stub_smtp.instances == []
