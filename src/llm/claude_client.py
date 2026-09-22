"""
Minimal Claude API client: the one place a model request is constructed.

Moved here from ``src/context/`` by backlog task 012 for Tier 2 adjudication.
Rewritten 2026-09-22 by task 026 (Phase 0 of ``docs/PLAN.md``) with three
changes and two outages kept, made synchronous by task 029 the same day, and
given a failure classification by 029's verification follow-up.

**Changes.**

1. **Every request is audited before it is sent** (:mod:`src.llm.audit`), and
   the usage the API reports is audited after. There is no argument that turns
   this off. The repository had no token accounting at all before this; the
   cost claims in the monitoring plan were unfalsifiable.
2. **The key comes from the OS keychain** (:mod:`src.config.credentials`), read
   when the client is constructed, never at import. A missing key is
   :class:`~src.config.credentials.MissingCredential`, raised where the request
   would have been built, with the command that fixes it.
3. **The model is chosen by role, not at the call site.** ``role="triage"``
   reads ``settings.llm_triage_model``; ``role="synthesis"`` reads
   ``settings.llm_synthesis_model``. Decided 2026-09-22: Sonnet 5 adjudicates,
   Opus 5 writes. ``effort`` is the ``output_config`` named parameter, and a
   structured-output schema goes beside it as ``output_config.format`` -- a
   request parameter, not a parsing convention.

**Failures are classified, because the caller's right response differs.**
:class:`ModelCallFailed.outcome` is one of three words. ``answered``: the API
answered and the answer is unusable (a refusal, a reply cut off at
``max_tokens``, no text block) or it rejected this one request as too large;
that is a fact about the pair and a caller may record it. ``rejected``: the
API rejected the request itself (400, 401, 403, 404) -- a bad schema, a bad
key, a retired model -- which is the operator's problem. ``unavailable``: a
connection error, a timeout, a 429, a 5xx or an overload; asking again later
is the right response. Only the SDK's own ``APIError`` family is classified;
any other exception is audited and re-raised untouched, because a ``TypeError``
from a kwarg the SDK no longer accepts is a bug, not a verdict.

**Synchronous** (task 029): the only caller is the adjudication loop inside a
click command, one pair at a time.

**Outages kept**, because a rewrite from a blank file reintroduces them: see
:data:`_response_text` (the ``ThinkingBlock`` shape change and the refusal
rule) and the model note in ``__init__`` (a retired model that failed silently
for ten weeks).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from anthropic import (
    Anthropic,
    APIError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RequestTooLargeError,
)

from ..config import credentials
from ..config.settings import settings
from . import audit

logger = logging.getLogger(__name__)

__all__ = ["EFFORT_LEVELS", "ROLES", "ClaudeClient", "ModelCallFailed", "ModelResponse"]

EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# role -> the settings attribute naming its model. Two roles, two settings, no
# model string anywhere else.
ROLES: dict[str, str] = {
    "triage": "llm_triage_model",
    "synthesis": "llm_synthesis_model",
}

Outcome = Literal["answered", "rejected", "unavailable"]

# The API errors that mean the request, not the answer, is wrong.
_REQUEST_ERRORS = (BadRequestError, AuthenticationError, PermissionDeniedError, NotFoundError)


class ModelCallFailed(RuntimeError):
    """
    An audited call that yielded no usable text. See the module docstring for
    the three outcomes. Carries the audit id the request was logged under and
    the usage the API reported (zeros when it never answered), so a caller
    recording the failure can cite the log entry and the cost.

    Added 2026-09-22 (backlog task 029).
    """

    def __init__(
        self,
        message: str,
        *,
        audit_id: str,
        outcome: Outcome,
        input_tokens: int = 0,
        output_tokens: int = 0,
        stop_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.audit_id = audit_id
        self.outcome: Outcome = outcome
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.stop_reason = stop_reason

    @property
    def misconfigured(self) -> bool:
        return self.outcome == "rejected"


def _classify(exc: APIError) -> Outcome:
    if isinstance(exc, _REQUEST_ERRORS):
        return "rejected"
    if isinstance(exc, RequestTooLargeError):
        return "answered"  # this one request is too large; that is a fact about the pair
    return "unavailable"


@dataclass(frozen=True)
class ModelResponse:
    """What a call returned, and what it cost. ``audit_id`` finds it in the log."""

    text: str
    model: str
    stop_reason: str | None
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    audit_id: str


def _response_text(response) -> str:
    """Pull the assistant's text out of a response.

    Added 2026-08-26. ``content[0].text`` was correct when the model did not
    think: the first block was always the text. This model thinks by default,
    so ``content[0]`` is a ThinkingBlock and indexing it raises AttributeError
    -- which is what happened on the first live run after the model migration.
    The block list is heterogeneous; select by type rather than by position.

    A refusal is raised rather than returned. Returning empty string would let
    a refused analysis flow downstream as if the model had simply found
    nothing to say, which is a different and much quieter failure.
    """
    if getattr(response, "stop_reason", None) == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise RuntimeError(f"Model declined the request (category: {category})")

    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    if not parts:
        kinds = [getattr(b, "type", "?") for b in response.content]
        raise RuntimeError(f"No text block in response; got blocks: {kinds}")
    return "".join(parts)


def _usage(response) -> dict[str, int]:
    """The four token counts, as plain ints, zero when the API omits one."""
    usage = getattr(response, "usage", None)
    return {
        name: int(getattr(usage, name, None) or 0)
        for name in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        )
    }


class ClaudeClient:
    """One role, one model, one audited send path."""

    def __init__(
        self, role: str = "triage", *, api_key: str | None = None, model: str | None = None
    ):
        """
        Args:
            role: ``triage`` or ``synthesis``; picks the model from settings.
            api_key: Only for tests. Everything else reads the keychain.
            model: Only for tests. Everything else reads the role's setting.
        """
        if role not in ROLES:
            raise ValueError(f"role must be one of {sorted(ROLES)}, got {role!r}")
        self.role = role
        self.api_key = api_key or credentials.read(credentials.ANTHROPIC)
        # The SDK resends an identical request up to twice on a connection
        # error, a 429 or a 5xx. That is a transport retry of the same request,
        # not a second question, and the adjudicator's never-retried rule sits
        # above it; the audit log records the request once. (2026-09-22.)
        self.client = Anthropic(api_key=self.api_key, timeout=300.0)
        # 2026-08-26: claude-sonnet-4-20250514 was RETIRED on 2026-06-15 and returned
        # 404 for ten weeks while the CLI printed a duration and exited 0. The model
        # is a setting now so that the next retirement is a one-line change in one
        # place, and the audit log records which model actually served each call.
        self.model = model or str(getattr(settings, ROLES[role]))
        # max_tokens caps thinking AND response text together, and these models
        # think by default, so a low ceiling truncates a full answer mid-sentence.
        self.max_tokens = 32000

    def analyze(
        self,
        system_prompt: str,
        user_message: str,
        effort: str = "high",
        max_tokens: int | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        """One user turn."""
        return self.analyze_conversation(
            system_prompt,
            [{"role": "user", "content": user_message}],
            effort,
            max_tokens,
            output_schema,
        )

    def analyze_conversation(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        effort: str = "high",
        max_tokens: int | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        """
        Send a conversation and return the text with its usage.

        The request is written to the audit log before the call, the usage after
        it, and the exception in between if the call fails. A refusal is
        recorded as a response (it is one) and then raised. With
        ``output_schema`` the API constrains the reply to that JSON schema; the
        caller still validates what comes back.
        """
        if effort not in EFFORT_LEVELS:
            raise ValueError(f"effort must be one of {EFFORT_LEVELS}, got {effort!r}")

        output_config: dict[str, Any] = {"effort": effort}
        if output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "system": system_prompt,
            "messages": messages,
            "output_config": output_config,
        }
        audit_id = audit.record_request(self.role, request)

        try:
            response = self.client.messages.create(**request)
        except APIError as exc:
            audit.record_error(audit_id, exc)
            logger.error(f"Claude API error: {exc}")
            raise ModelCallFailed(
                f"{type(exc).__name__}: {exc}", audit_id=audit_id, outcome=_classify(exc)
            ) from exc
        except Exception as exc:
            # Not an API error: a bug, a version mismatch, an interrupt's cousin.
            # Audited so the log shows the request left, then re-raised as-is.
            audit.record_error(audit_id, exc)
            raise

        usage = _usage(response)
        stop_reason = getattr(response, "stop_reason", None)
        audit.record_response(
            audit_id,
            model=str(getattr(response, "model", self.model)),
            stop_reason=stop_reason,
            usage=usage,
        )
        try:
            text = _response_text(response)
        except RuntimeError as exc:
            raise ModelCallFailed(
                str(exc),
                audit_id=audit_id,
                outcome="answered",
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                stop_reason=stop_reason,
            ) from exc
        return ModelResponse(
            text=text,
            model=str(getattr(response, "model", self.model)),
            stop_reason=stop_reason,
            audit_id=audit_id,
            **usage,
        )
