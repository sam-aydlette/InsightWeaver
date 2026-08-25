"""
Email renderer.

Wraps :class:`~src.render.html.HTMLRenderer`: the HTML body is the same
self-contained document the ``html`` format writes, with a plain-text
alternative derived from the terminal rendering. Delivery uses the SMTP
environment variables the project already documents in ``.env``:

    SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD,
    FROM_EMAIL, RECIPIENT_EMAIL

There is no retry and no outbox. A failed send raises
:class:`EmailDeliveryError` and the caller exits non-zero.
"""

from __future__ import annotations

import os
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from .document import BriefDocument
from .html import HTMLRenderer
from .terminal import TerminalRenderer

__all__ = ["EmailDeliveryError", "EmailRenderer", "SMTPConfig"]

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Credentials are read from these but never echoed; only names appear in errors.
_REQUIRED_VARS = ("SMTP_SERVER", "EMAIL_USERNAME", "EMAIL_PASSWORD", "FROM_EMAIL")


class EmailDeliveryError(RuntimeError):
    """Configuration or transport failure while sending a brief."""


@dataclass(frozen=True)
class SMTPConfig:
    """SMTP settings, read from the environment at send time."""

    server: str
    port: int
    username: str
    password: str
    from_email: str
    recipient: str

    @classmethod
    def from_env(cls, recipient: str | None = None) -> SMTPConfig:
        """
        Read SMTP settings from the environment.

        Raises :class:`EmailDeliveryError` naming any missing variable. Values
        are never included in the message -- only variable names.
        """
        missing = [name for name in _REQUIRED_VARS if not os.getenv(name)]
        target = recipient or os.getenv("RECIPIENT_EMAIL") or ""
        if not target:
            missing.append("RECIPIENT_EMAIL")
        if missing:
            raise EmailDeliveryError(
                "Cannot send brief: missing environment variable(s): " + ", ".join(missing)
            )

        raw_port = os.getenv("SMTP_PORT", "587")
        try:
            port = int(raw_port)
        except ValueError:
            raise EmailDeliveryError(f"SMTP_PORT is not a number: {raw_port!r}")

        return cls(
            server=os.environ["SMTP_SERVER"],
            port=port,
            username=os.environ["EMAIL_USERNAME"],
            password=os.environ["EMAIL_PASSWORD"],
            from_email=os.environ["FROM_EMAIL"],
            recipient=target,
        )


class EmailRenderer:
    """Render a :class:`BriefDocument` as a sendable email message."""

    def __init__(
        self,
        html_renderer: HTMLRenderer | None = None,
        terminal_renderer: TerminalRenderer | None = None,
    ) -> None:
        self.html_renderer = html_renderer or HTMLRenderer()
        self.terminal_renderer = terminal_renderer or TerminalRenderer()

    def subject(self, doc: BriefDocument) -> str:
        """Subject line -- stable for a given stored run."""
        stamp = doc.date_stamp
        base = f"Intelligence Brief — {stamp}" if stamp else "Intelligence Brief"
        count = len(doc.situations)
        return f"{base} ({count} situation{'s' if count != 1 else ''})"

    def render_text(self, doc: BriefDocument) -> str:
        """Plain-text alternative: the terminal brief with color escapes removed."""
        return _ANSI.sub("", self.terminal_renderer.render(doc))

    def render(
        self,
        doc: BriefDocument,
        *,
        from_email: str = "",
        recipient: str = "",
    ) -> EmailMessage:
        """Build the multipart/alternative message for this brief."""
        message = EmailMessage()
        message["Subject"] = self.subject(doc)
        if from_email:
            message["From"] = from_email
        if recipient:
            message["To"] = recipient
        message.set_content(self.render_text(doc))
        message.add_alternative(self.html_renderer.render(doc), subtype="html")
        return message

    def send(
        self,
        doc: BriefDocument,
        *,
        recipient: str | None = None,
        config: SMTPConfig | None = None,
    ) -> str:
        """
        Send the brief. Returns the recipient address on success.

        Raises :class:`EmailDeliveryError` on any configuration or transport
        failure -- no retry, no queueing.
        """
        cfg = config or SMTPConfig.from_env(recipient)
        message = self.render(doc, from_email=cfg.from_email, recipient=cfg.recipient)

        try:
            if cfg.port == 465:
                with smtplib.SMTP_SSL(cfg.server, cfg.port, timeout=30) as smtp:
                    smtp.login(cfg.username, cfg.password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(cfg.server, cfg.port, timeout=30) as smtp:
                    smtp.starttls()
                    smtp.login(cfg.username, cfg.password)
                    smtp.send_message(message)
        # smtplib.SMTPException derives from OSError, so this covers both
        # protocol-level rejections and connection/DNS/TLS failures.
        except OSError as exc:
            raise EmailDeliveryError(
                f"Sending the brief to {cfg.recipient} via {cfg.server}:{cfg.port} failed: {exc}"
            )
        return cfg.recipient
