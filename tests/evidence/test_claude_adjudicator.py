"""
The one model adjudicator: what it sends, what it accepts, what it refuses.

No test here makes a network call. The client is replaced with a stub whose
``analyze`` returns a scripted :class:`ModelResponse`, so the tests cover the
adjudicator's own promises: the prompt is pinned to its version, a verdict is
validated on receipt, a failure is recorded once and never retried, and the
protocol method only ever sees routed watches.
"""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from src.config import credentials
from src.database.models import Watch
from src.evidence import ObservationView, Verdict, known_prompt_versions, resolve
from src.evidence.claude_adjudicator import (
    PROMPT_FINGERPRINT,
    PROMPT_VERSION,
    SCHEMA,
    AdjudicationFailed,
    AdjudicationVerdict,
    ClaudeAdjudicator,
    api_schema,
)
from src.evidence.prompt import EFFORT, MAX_TOKENS, TEXT_CAP, build_messages, estimate_tokens
from src.llm.claude_client import ModelCallFailed, ModelResponse

# Change the prompt, the effort, the schema, the cap or max_tokens and this
# changes; then PROMPT_VERSION must change too, or two different judges share
# one name in every evidence row. The value was computed on 2026-09-22.
PINNED_FINGERPRINT = (
    "403f818d93aeaec77c27c654b14865114962914daae0530d224d98220a5a7a81"  # pragma: allowlist secret
)


def _watch(**overrides) -> Watch:
    fields = {
        "id": "conmon-scope-expands",
        "claim": "Continuous monitoring scope expands before the assessment window.",
        "belief": 0.35,
        "decision_key": "renew-authorization",
        "so_what": "Scope expansion moves renewal past the point where lapsing is cheaper.",
        "triggers": [{"terms": ["continuous monitoring", "conmon"]}, {"sources": ["FR"]}],
        "expires": date(2027, 3, 31),
        "staleness_alert_days": 30,
    }
    fields.update(overrides)
    return Watch(**fields)


def _view(text="The agency expanded continuous monitoring today.", **payload) -> ObservationView:
    base = {
        "title": "Agency expands continuous monitoring scope",
        "normalized_content": text,
        "source_url": "https://example.gov/api",
        "published_date": "2026-08-20T09:00:00",
    }
    base.update(payload)
    return ObservationView(content_hash="sha256:abc", payload=base)


def _verdict(**overrides) -> str:
    body = {
        "is_evidence": True,
        "direction": "supports",
        "magnitude": 0.7,
        "satisfies_clause": 0,
        "confidence": 0.8,
        "rationale": "The text says scope expanded.",
    }
    body.update(overrides)
    return json.dumps(body)


def _response(text: str, stop_reason: str = "end_turn") -> ModelResponse:
    return ModelResponse(
        text=text,
        model="m",
        stop_reason=stop_reason,
        input_tokens=120,
        output_tokens=30,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        audit_id="audit-1",
    )


class FakeClient:
    """Answers each call with the next scripted text, or raises the next error."""

    def __init__(self, *scripted):
        self.scripted = list(scripted)
        self.calls: list[dict] = []

    def analyze(self, system_prompt, user_message, **kwargs):
        self.calls.append({"system": system_prompt, "user": user_message, **kwargs})
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            return _response(*item)
        return _response(item)


class TestPromptIdentity:
    def test_the_prompt_fingerprint_is_pinned_to_the_version(self):
        assert PROMPT_VERSION == "claude-v1"
        assert PROMPT_FINGERPRINT == PINNED_FINGERPRINT, (
            "the prompt, effort, schema, text cap or max_tokens changed: bump PROMPT_VERSION "
            "and update PINNED_FINGERPRINT in the same commit"
        )

    def test_the_version_is_registered_without_building_a_client(self, monkeypatch):
        def explode(*_args, **_kwargs):
            raise AssertionError("a client was constructed")

        monkeypatch.setattr("src.evidence.claude_adjudicator.ClaudeClient", explode)

        assert "claude-v1" in known_prompt_versions()
        adjudicator = resolve("claude-v1")
        assert isinstance(adjudicator, ClaudeAdjudicator)
        build_messages(_view(), _watch())


class TestMessages:
    def test_the_user_message_carries_the_claim_the_stake_and_the_indexed_clauses(self):
        system, user = build_messages(_view(), _watch())

        assert system.startswith("You judge whether one published item")
        assert "Continuous monitoring scope expands" in user
        assert "renew-authorization" in user
        assert "lapsing is cheaper" in user
        assert "0: terms: continuous monitoring, conmon" in user
        assert "1: sources: FR" in user
        assert "source: https://example.gov/api" in user
        assert "published: 2026-08-20T09:00:00" in user
        assert "title: Agency expands continuous monitoring scope" in user

    def test_long_text_is_capped_and_the_message_says_so(self):
        long_text = "x" * (TEXT_CAP + 500)

        _system, user = build_messages(_view(text=long_text), _watch())

        assert f"{TEXT_CAP + 500} characters, truncated to {TEXT_CAP}" in user
        body = user.rsplit("):\n", 1)[1]  # the text line is the last one in the template
        assert body == "x" * TEXT_CAP

    def test_short_text_is_sent_whole_with_its_length(self):
        _system, user = build_messages(_view(text="short body"), _watch())

        assert "text (10 characters):" in user
        assert "truncated" not in user

    def test_the_estimate_is_a_character_count_not_a_token_count(self):
        assert estimate_tokens("a" * 40, "b" * 40) == 20


class TestVerdictValidation:
    def test_a_well_formed_verdict_validates(self):
        verdict = AdjudicationVerdict.model_validate_json(_verdict())
        assert verdict.direction == "supports"

    def test_evidence_without_a_direction_is_refused(self):
        with pytest.raises(ValidationError, match="must carry a direction"):
            AdjudicationVerdict.model_validate_json(_verdict(direction="none"))

    def test_non_evidence_with_a_direction_is_refused(self):
        with pytest.raises(ValidationError, match="carries no direction"):
            AdjudicationVerdict.model_validate_json(_verdict(is_evidence=False))

    @pytest.mark.parametrize(
        "field, value",
        [("magnitude", 1.5), ("confidence", -0.1), ("direction", "maybe"), ("rationale", "")],
    )
    def test_out_of_range_fields_are_refused(self, field, value):
        with pytest.raises(ValidationError):
            AdjudicationVerdict.model_validate_json(_verdict(**{field: value}))

    def test_an_unexpected_field_is_refused(self):
        with pytest.raises(ValidationError):
            AdjudicationVerdict.model_validate_json(_verdict(recommendation="sell"))

    def test_the_schema_sent_to_the_api_is_derived_from_the_model(self):
        assert api_schema(AdjudicationVerdict) == SCHEMA
        assert set(SCHEMA["required"]) == set(AdjudicationVerdict.model_fields)
        assert set(SCHEMA["properties"]) == set(AdjudicationVerdict.model_fields)
        assert SCHEMA["properties"]["direction"]["enum"] == ["supports", "contradicts", "none"]
        assert SCHEMA["additionalProperties"] is False

    def test_the_schema_carries_no_keyword_the_api_rejects(self):
        rejected = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength"}

        def keys(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield k
                    yield from keys(v)
            elif isinstance(node, list):
                for item in node:
                    yield from keys(item)

        assert rejected.isdisjoint(set(keys(SCHEMA)))
        # The ranges still hold on receipt, where pydantic enforces them.
        assert "0 to 1" in SCHEMA["properties"]["magnitude"]["description"]


class TestJudge:
    def test_a_valid_evidence_verdict_is_returned_with_its_cost(self):
        client = FakeClient(_verdict())
        judgement = ClaudeAdjudicator(client).judge(_view(), _watch())

        assert judgement.outcome == "evidence"
        assert judgement.verdict is not None
        assert judgement.verdict.magnitude == 0.7
        assert judgement.error is None
        assert judgement.audit_id == "audit-1"
        assert (judgement.input_tokens, judgement.output_tokens) == (120, 30)

    def test_the_call_uses_the_versioned_effort_cap_and_schema(self):
        client = FakeClient(_verdict())
        ClaudeAdjudicator(client).judge(_view(), _watch())

        (call,) = client.calls
        assert call["effort"] == EFFORT
        assert call["max_tokens"] == MAX_TOKENS
        assert call["output_schema"] is SCHEMA

    def test_a_reply_cut_off_at_max_tokens_is_a_failure_that_names_the_cause(self):
        client = FakeClient(('{"is_evidence": true', "max_tokens"))
        judgement = ClaudeAdjudicator(client).judge(_view(), _watch())

        assert judgement.outcome == "failed"
        assert "max_tokens" in (judgement.error or "")
        assert judgement.audit_id == "audit-1"

    def test_a_clause_index_the_watch_does_not_have_is_a_failure(self):
        client = FakeClient(_verdict(satisfies_clause=7))
        judgement = ClaudeAdjudicator(client).judge(_view(), _watch())

        assert judgement.outcome == "failed"
        assert "satisfies_clause 7" in (judgement.error or "")

    def test_a_missing_key_raises_before_the_call_and_is_not_a_verdict(self, memory_keyring):
        with pytest.raises(credentials.MissingCredential):
            ClaudeAdjudicator().judge(_view(), _watch())

    def test_a_none_verdict_is_recorded_as_none(self):
        client = FakeClient(_verdict(is_evidence=False, direction="none", satisfies_clause=-1))
        judgement = ClaudeAdjudicator(client).judge(_view(), _watch())

        assert judgement.outcome == "none"
        assert judgement.error is None

    def test_malformed_json_is_a_failure_with_the_cost_kept(self):
        client = FakeClient("not json at all")
        judgement = ClaudeAdjudicator(client).judge(_view(), _watch())

        assert judgement.outcome == "failed"
        assert judgement.verdict is None
        assert judgement.error is not None and judgement.error.startswith("invalid verdict")
        assert judgement.audit_id == "audit-1"
        assert judgement.input_tokens == 120

    def test_a_refusal_or_api_error_is_a_failure_with_its_cost_and_is_not_retried(self):
        refusal = ModelCallFailed(
            "Model declined the request (category: x)",
            audit_id="audit-r",
            input_tokens=400,
            output_tokens=2,
            stop_reason="refusal",
        )
        client = FakeClient(refusal, _verdict())
        judgement = ClaudeAdjudicator(client).judge(_view(), _watch())

        assert judgement.outcome == "failed"
        assert judgement.error == "Model declined the request (category: x)"
        assert judgement.audit_id == "audit-r"
        assert (judgement.input_tokens, judgement.output_tokens) == (400, 2)
        assert len(client.calls) == 1, "a failed call must not be retried"
        assert client.scripted == [_verdict()], "the second scripted answer was never consumed"

    def test_a_rejected_request_aborts_rather_than_becoming_a_verdict(self):
        """A 400 or 401 is the operator's problem; no pair may be marked failed by it."""
        rejected = ModelCallFailed("BadRequestError: schema", audit_id="a", misconfigured=True)
        client = FakeClient(rejected, _verdict())

        with pytest.raises(ModelCallFailed, match="schema"):
            ClaudeAdjudicator(client).judge(_view(), _watch())

    def test_an_unexpected_exception_is_not_swallowed_into_a_verdict(self):
        """Only the typed model failure is recorded; a bug propagates."""
        client = FakeClient(TypeError("a programming error"))

        with pytest.raises(TypeError):
            ClaudeAdjudicator(client).judge(_view(), _watch())

    def test_a_validation_failure_is_not_coerced_into_a_verdict(self):
        client = FakeClient(_verdict(is_evidence=True, direction="none"))
        judgement = ClaudeAdjudicator(client).judge(_view(), _watch())

        assert judgement.outcome == "failed"
        assert "must carry a direction" in (judgement.error or "")


class TestProtocol:
    def test_adjudicate_returns_a_verdict_per_evidence_answer(self):
        client = FakeClient(_verdict(), _verdict(is_evidence=False, direction="none"))
        verdicts = ClaudeAdjudicator(client).adjudicate(_view(), [_watch(), _watch(id="other")])

        assert verdicts == [
            Verdict(
                watch_id="conmon-scope-expands",
                direction="supports",
                magnitude=0.7,
                rationale="The text says scope expanded.",
            )
        ]

    def test_adjudicate_raises_on_a_failure_rather_than_dropping_the_pair(self):
        client = FakeClient("garbage")

        with pytest.raises(AdjudicationFailed, match="failed"):
            ClaudeAdjudicator(client).adjudicate(_view(), [_watch()])


def test_only_the_adjudicator_constructs_a_client():
    """
    Invariant 4 as a tree property: one module makes model requests, and it
    is this one. ``src/llm/claude_client.py`` defines the class and is excluded.
    """
    import re
    from pathlib import Path

    # A literal-token check: a subclass or an alias would slip past it, and
    # the companion test in tests/llm/test_claude_client.py pins the SDK
    # constructor the same way. Both are gates against habit, not adversaries.
    root = Path(__file__).resolve().parents[2] / "src"
    pattern = re.compile(r"\bClaudeClient\(")
    allowed = {root / "llm" / "claude_client.py", root / "evidence" / "claude_adjudicator.py"}
    offenders = [
        str(p.relative_to(root))
        for p in sorted(root.rglob("*.py"))
        if p not in allowed and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"a client is constructed outside the adjudicator: {offenders}"
