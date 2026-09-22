"""
The one model adjudicator: one structured call per routed pair, nothing retried.

This is the single stochastic component in the system (invariant 4), and the
only module that constructs a :class:`~src.llm.claude_client.ClaudeClient`,
asserted against the tree by tests/evidence/test_claude_adjudicator.py. It
judges one observation against one pre-registered claim and returns a verdict
the schema below validates, or a recorded failure. It never returns a guess.

**Why the prompt is fingerprinted.** Every evidence row carries
``prompt_version``, and replay compares versions. A prompt edited without a
version bump would label two different judges with one name, which is the
mislabelled-corpus failure task 014 was built to prevent. So the prompt text,
the effort, the caps and the response schema are hashed into
:data:`PROMPT_FINGERPRINT`, and a test pins that hash to
:data:`PROMPT_VERSION`; change any of them and the test says to bump the
version.

**Why failures are recorded and not retried.** A retry that produces a
different answer to the same input breaks replay determinism, the only
mechanism for reviewing a prompt change. A refusal, an API error, a reply cut
off at ``max_tokens``, or a reply that fails validation becomes an
``adjudications`` row with ``outcome='failed'`` and the error text, with the
audit id and the tokens the failed call still cost. The SDK's own transport
retries (a 429 or a 5xx answered by an identical resend) are below this rule
and are noted in ``src/llm/claude_client.py``.

**What is not a failure of the model.** A missing keychain entry, or any
other error constructing the client, is raised before any pair is asked; a
request the API rejects outright (a 400 for a malformed schema, a 401, a 404
for a retired model) is raised from the pair it hit. Both are the operator's
problem, and recording either as a verdict would leave every pending pair
permanently "failed" without a single answer having been given.

**Why the schema uses sentinels.** The task file wrote ``direction`` and
``satisfies_clause`` as nullable. The API's structured-output grammar takes a
flat enum and an integer with no union, so ``direction`` is three-valued with
``"none"`` and ``satisfies_clause`` is ``-1`` for no clause; the pydantic
validator enforces the same rule the nullable form would have (evidence must
carry a direction). Recorded 2026-09-22.

**What the model sees.** The watch's claim, the decision it serves, its
trigger clauses with indices, and the observation's source, date, title and
text, the text capped at :data:`~src.evidence.prompt.TEXT_CAP` characters with
the cap stated in the message so the audit log records that it applied.
Nothing else: no other watches, no Position, no belief.

Added 2026-09-22 for backlog task 029.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..llm.claude_client import ClaudeClient, ModelCallFailed
from .adjudicator import ObservationView, Verdict
from .prompt import EFFORT, MAX_TOKENS, SYSTEM_PROMPT, TEXT_CAP, USER_TEMPLATE, build_messages

__all__ = [
    "PROMPT_FINGERPRINT",
    "PROMPT_VERSION",
    "SCHEMA",
    "AdjudicationFailed",
    "AdjudicationVerdict",
    "ClaudeAdjudicator",
    "Judgement",
    "api_schema",
]

PROMPT_VERSION = "claude-v1"

# JSON Schema keywords the structured-output grammar does not accept. The
# ranges they expressed are enforced by pydantic on receipt and stated in the
# field descriptions the model reads. (2026-09-22, backlog task 029.)
_UNSUPPORTED_KEYS = frozenset(
    {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "title"}
)


class AdjudicationVerdict(BaseModel):
    """
    The structured answer. Validated on receipt; a bad one is a failure, not a
    default.

    ``magnitude`` is the strength of bearing on the claim, not a probability
    that the claim is true. ``confidence`` is the model's confidence in its own
    reading of the text. Both are recorded on the ``adjudications`` row, with
    ``satisfies_clause`` and the rationale; neither moves belief.
    """

    model_config = ConfigDict(extra="forbid")

    is_evidence: bool = Field(description="Whether the item bears on the claim at all.")
    direction: Literal["supports", "contradicts", "none"] = Field(
        description='"supports" or "contradicts" when is_evidence is true; "none" otherwise.'
    )
    magnitude: float = Field(
        ge=0.0, le=1.0, description="Strength of bearing, 0 to 1. Not a probability."
    )
    satisfies_clause: int = Field(
        ge=-1, description="Index of the trigger clause the item satisfies, or -1."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in your reading of the text, 0 to 1."
    )
    rationale: str = Field(
        min_length=1, description="One or two sentences quoting the words the verdict rests on."
    )

    @model_validator(mode="after")
    def _evidence_has_a_direction(self) -> AdjudicationVerdict:
        if self.is_evidence and self.direction == "none":
            raise ValueError("a verdict that is evidence must carry a direction")
        if not self.is_evidence and self.direction != "none":
            raise ValueError("a verdict that is not evidence carries no direction")
        return self


def api_schema(model: type[BaseModel]) -> dict[str, Any]:
    """The model's JSON schema with the keywords the API rejects removed."""

    def strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in _UNSUPPORTED_KEYS}
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    schema = strip(model.model_json_schema())
    schema["additionalProperties"] = False
    return schema


SCHEMA: dict[str, Any] = api_schema(AdjudicationVerdict)


def _fingerprint() -> str:
    material = json.dumps(
        {
            "system": SYSTEM_PROMPT,
            "user": USER_TEMPLATE,
            "effort": EFFORT,
            "schema": SCHEMA,
            "text_cap": TEXT_CAP,
            "max_tokens": MAX_TOKENS,
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


PROMPT_FINGERPRINT = _fingerprint()


class AdjudicationFailed(RuntimeError):
    """Raised by the replay-harness path when a pair cannot be judged."""


@dataclass(frozen=True)
class Judgement:
    """What one call produced: a verdict, or the error that stands in for one."""

    watch_id: str
    verdict: AdjudicationVerdict | None
    error: str | None
    audit_id: str | None
    input_tokens: int
    output_tokens: int

    @property
    def outcome(self) -> str:
        if self.error is not None:
            return "failed"
        assert self.verdict is not None
        return "evidence" if self.verdict.is_evidence else "none"


class ClaudeAdjudicator:
    """
    Prompt version ``claude-v1``.

    The client is built on first use, not at construction, so registering the
    adjudicator, listing versions and ``--dry-run`` never touch the keychain.
    """

    prompt_version = PROMPT_VERSION

    def __init__(self, client: ClaudeClient | None = None) -> None:
        self._client = client

    def client(self) -> ClaudeClient:
        """The client, built on first use. A missing key raises here, loudly."""
        if self._client is None:
            self._client = ClaudeClient("triage")
        return self._client

    def judge(self, observation: ObservationView, watch: Any) -> Judgement:
        """
        One call, one recorded outcome.

        Model-side failures (refusal, API error, truncation, an invalid reply)
        come back as a :class:`Judgement` with ``error`` set and the call's
        audit id and cost kept. A client that cannot be built raises before
        any call is made.
        """
        client = self.client()
        system, user = build_messages(observation, watch)
        watch_id = str(watch.id)
        try:
            response = client.analyze(
                system, user, effort=EFFORT, max_tokens=MAX_TOKENS, output_schema=SCHEMA
            )
        except ModelCallFailed as exc:
            if exc.misconfigured:
                # The request was rejected, not answered: a bad schema, a bad
                # key, a retired model. Recording that per pair would mark every
                # pending pair failed with no verdict ever given. Abort instead.
                raise
            return Judgement(
                watch_id, None, str(exc), exc.audit_id, exc.input_tokens, exc.output_tokens
            )
        cost = (response.audit_id, response.input_tokens, response.output_tokens)
        if response.stop_reason == "max_tokens":
            return Judgement(watch_id, None, f"reply cut off at max_tokens={MAX_TOKENS}", *cost)
        try:
            verdict = AdjudicationVerdict.model_validate_json(response.text)
        except ValidationError as exc:
            return Judgement(
                watch_id, None, f"invalid verdict: {exc.error_count()} error(s): {exc}", *cost
            )
        clause_count = len(watch.triggers or ())
        if verdict.satisfies_clause >= clause_count:
            return Judgement(
                watch_id,
                None,
                f"invalid verdict: satisfies_clause {verdict.satisfies_clause} names a clause "
                f"the watch does not have ({clause_count} clause(s))",
                *cost,
            )
        return Judgement(watch_id, verdict, None, *cost)

    def adjudicate(self, observation: ObservationView, watches: Sequence[Any]) -> list[Verdict]:
        """
        The replay-harness protocol: verdicts for the watches given.

        A failed call raises :class:`AdjudicationFailed` here rather than being
        swallowed, because replay has no ledger to record it in and a silently
        missing row would read as "not evidence". One failure ends the replay;
        ``insightweaver adjudicate`` is the path that records and continues.
        """
        verdicts = []
        for watch in watches:
            judgement = self.judge(observation, watch)
            if judgement.error is not None:
                raise AdjudicationFailed(
                    f"adjudication of {observation.content_hash} against {watch.id} failed: "
                    f"{judgement.error}"
                )
            assert judgement.verdict is not None
            if judgement.verdict.is_evidence:
                verdicts.append(
                    Verdict(
                        watch_id=str(watch.id),
                        direction=judgement.verdict.direction,
                        magnitude=judgement.verdict.magnitude,
                        rationale=judgement.verdict.rationale,
                    )
                )
        return verdicts
