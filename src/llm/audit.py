"""
The local audit log of everything that leaves this machine for a model.

One rule: **a request is written here before it is sent, and there is no way to
send one without writing it.** :class:`~src.llm.claude_client.ClaudeClient` is
the only module that constructs a model request, and its send path calls
:func:`record_request` first. The operator can therefore answer "what left my
machine, when, and what came back" by reading a file, without trusting the
code that sent it.

Format: JSON lines under ``settings.llm_audit_dir``, one file per UTC day.
Three event kinds share an ``id``:

* ``request`` -- the full request body as sent (model, system, messages,
  ``output_config``, ``max_tokens``), plus a SHA-256 of its canonical JSON so
  two runs can be compared without diffing prose.
* ``response`` -- the usage block, stop reason and model the API reported. Not
  the response text: that is the caller's to store, and the log is about what
  was *sent*.
* ``error`` -- the exception, when the send failed after the request was
  written. A request with no response and no error line is one that was
  written while the process died; that is visible, which is the point.

The log is not a cache and not a replay input. Evidence replay reads
``observations``; this file is for the operator's eyes.

Added 2026-09-22 for backlog task 026 (Phase 0 of ``docs/PLAN.md``).
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config.settings import settings

__all__ = ["record_error", "record_request", "record_response"]


def _now() -> datetime:
    return datetime.now(UTC)


def _path(when: datetime) -> Path:
    directory = Path(settings.llm_audit_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{when.date().isoformat()}.jsonl"


def _append(event: dict[str, Any]) -> None:
    when = _now()
    event = {"at": when.isoformat(timespec="seconds"), **event}
    with _path(when).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
        handle.flush()


def _canonical(request: dict[str, Any]) -> str:
    return json.dumps(request, sort_keys=True, separators=(",", ":"), default=str)


def record_request(role: str, request: dict[str, Any]) -> str:
    """Write the request body as it will be sent. Returns the entry id."""
    entry_id = secrets.token_hex(8)
    body = _canonical(request)
    _append(
        {
            "id": entry_id,
            "event": "request",
            "role": role,
            "payload_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "request": request,
        }
    )
    return entry_id


def record_response(entry_id: str, *, model: str, stop_reason: str | None, usage: dict) -> None:
    """Write what the API reported about the request: usage and stop reason."""
    _append(
        {
            "id": entry_id,
            "event": "response",
            "model": model,
            "stop_reason": stop_reason,
            "usage": usage,
        }
    )


def record_error(entry_id: str, error: BaseException) -> None:
    """Write that the send failed. The request line above it still stands."""
    _append({"id": entry_id, "event": "error", "error": f"{type(error).__name__}: {error}"})
