"""
The adjudication run: every routed pair once, every outcome recorded.

The corpus is the replay stubs' four items and two watches, routed with the
real router, so two pairs are pending. The adjudicator's client is a stub that
answers from a script; no network, no key.
"""

import json

import pytest

from src.config import credentials
from src.database.models import Adjudication, Evidence
from src.evidence import commit, rebuild
from src.evidence.adjudicate import dry_run, pending_pairs, run
from src.evidence.claude_adjudicator import PROMPT_VERSION, ClaudeAdjudicator
from src.llm.claude_client import ModelCallFailed, ModelResponse

from .stubs import KeywordAdjudicator


def _verdict(is_evidence=True, direction="supports", **overrides) -> str:
    body = {
        "is_evidence": is_evidence,
        "direction": direction,
        "magnitude": 0.6,
        "satisfies_clause": 0 if is_evidence else -1,
        "confidence": 0.8,
        "rationale": "quoted words",
    }
    body.update(overrides)
    return json.dumps(body)


class FakeClient:
    def __init__(self, *scripted):
        self.scripted = list(scripted)
        self.calls = 0

    def analyze(self, system_prompt, user_message, **kwargs):
        self.calls += 1
        item = self.scripted.pop(0)
        if isinstance(item, BaseException):
            raise item
        return ModelResponse(
            text=item,
            model="m",
            stop_reason="end_turn",
            input_tokens=100,
            output_tokens=10,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            audit_id=f"audit-{self.calls}",
        )


@pytest.fixture
def corpus(test_session, observations):
    """The routed stub corpus: doc-1 -> conmon, doc-2 -> hiring."""
    return test_session


class TestPendingPairs:
    def test_the_routed_pairs_are_pending_in_a_fixed_order(self, corpus):
        pairs = pending_pairs(corpus, PROMPT_VERSION)

        assert [p.watch.id for p in pairs] == sorted(p.watch.id for p in pairs)
        assert {p.watch.id for p in pairs} == {"conmon-scope-expands", "hiring-market-tightens"}
        assert all(p.view.payload["title"] for p in pairs)

    def test_a_pair_already_answered_under_this_version_is_not_pending(self, corpus):
        run(corpus, ClaudeAdjudicator(FakeClient(_verdict(), _verdict())))

        assert pending_pairs(corpus, PROMPT_VERSION) == []
        assert len(pending_pairs(corpus, "some-other-version")) == 2

    def test_a_pair_with_evidence_committed_by_replay_is_not_asked_again(self, corpus):
        """`replay --commit` writes evidence but no ledger row; that still counts as answered."""
        commit(corpus, PROMPT_VERSION, rebuild(corpus, KeywordAdjudicator(PROMPT_VERSION)))

        assert pending_pairs(corpus, PROMPT_VERSION) == []
        result = run(corpus, ClaudeAdjudicator(FakeClient()))
        assert result.asked == 0

    def test_expiry_is_routing_s_gate_not_adjudication_s(self, corpus):
        """A routed pair on a watch that has since expired is still asked once."""
        from datetime import date

        from src.database.models import Watch

        corpus.get(Watch, "hiring-market-tightens").expires = date(2020, 1, 1)
        corpus.flush()

        assert {p.watch.id for p in pending_pairs(corpus, PROMPT_VERSION)} == {
            "conmon-scope-expands",
            "hiring-market-tightens",
        }
        assert {r.watch_id for r in rebuild(corpus, KeywordAdjudicator("v1"))} == {
            "conmon-scope-expands",
            "hiring-market-tightens",
        }

    def test_a_retired_or_resolved_watch_s_pairs_are_not_pending(self, corpus):
        """A state the operator set, not a date: asking about a closed watch costs for nothing."""
        from datetime import datetime

        from src.database.models import Watch
        from src.position.ledger import resolve_watch

        corpus.get(Watch, "conmon-scope-expands").retired_at = datetime(2026, 8, 30)
        resolve_watch(corpus, "hiring-market-tightens", outcome="yes", note="settled")
        corpus.flush()

        assert pending_pairs(corpus, PROMPT_VERSION) == []
        assert rebuild(corpus, KeywordAdjudicator("v1")) == []

    def test_limit_narrows_the_run_and_zero_is_refused(self, corpus):
        assert len(pending_pairs(corpus, PROMPT_VERSION, limit=1)) == 1
        with pytest.raises(ValueError, match="at least 1"):
            pending_pairs(corpus, PROMPT_VERSION, limit=0)


class TestRun:
    def test_every_pair_gets_a_ledger_row_and_evidence_gets_an_evidence_row(self, corpus):
        client = FakeClient(_verdict(), _verdict(is_evidence=False, direction="none"))

        result = run(corpus, ClaudeAdjudicator(client))

        assert (result.asked, result.evidence, result.none, result.failed) == (2, 1, 1, 0)
        assert (result.input_tokens, result.output_tokens) == (200, 20)
        ledger = corpus.query(Adjudication).order_by(Adjudication.watch_id).all()
        assert [(a.watch_id, a.outcome, a.audit_id) for a in ledger] == [
            ("conmon-scope-expands", "evidence", "audit-1"),
            ("hiring-market-tightens", "none", "audit-2"),
        ]
        evidence = corpus.query(Evidence).all()
        assert [(e.watch_id, e.direction, e.prompt_version) for e in evidence] == [
            ("conmon-scope-expands", "supports", PROMPT_VERSION)
        ]

    def test_the_rest_of_a_verdict_is_kept_on_the_ledger_for_none_verdicts_too(self, corpus):
        client = FakeClient(_verdict(), _verdict(is_evidence=False, direction="none"))

        run(corpus, ClaudeAdjudicator(client))

        rows = {a.outcome: a for a in corpus.query(Adjudication).all()}
        assert (rows["evidence"].confidence, rows["evidence"].satisfies_clause) == (0.8, 0)
        assert (rows["none"].confidence, rows["none"].satisfies_clause) == (0.8, -1)
        assert rows["none"].rationale == "quoted words"

    def test_a_second_run_asks_nothing(self, corpus):
        client = FakeClient(_verdict(), _verdict())
        run(corpus, ClaudeAdjudicator(client))

        second = run(corpus, ClaudeAdjudicator(client))

        assert second.asked == 0
        assert client.calls == 2
        assert corpus.query(Adjudication).count() == 2

    def test_a_failure_is_recorded_with_its_error_and_cost_and_writes_no_evidence(self, corpus):
        client = FakeClient("not json", _verdict())

        result = run(corpus, ClaudeAdjudicator(client))

        assert result.failed == 1
        assert result.evidence == 1
        failed = corpus.query(Adjudication).filter(Adjudication.outcome == "failed").one()
        assert failed.error is not None and failed.error.startswith("invalid verdict")
        assert failed.input_tokens == 100  # the failed call still cost something
        assert failed.audit_id == "audit-1"
        assert failed.rationale is None
        assert result.failures == [(failed.observation_hash, failed.watch_id, failed.error)]
        assert corpus.query(Evidence).count() == 1

    def test_a_refused_call_keeps_its_audit_id_and_cost_on_the_ledger(self, corpus):
        refusal = ModelCallFailed(
            "Model declined the request (category: x)",
            audit_id="audit-refused",
            outcome="answered",
            input_tokens=500,
            output_tokens=3,
            stop_reason="refusal",
        )
        client = FakeClient(refusal, _verdict())

        result = run(corpus, ClaudeAdjudicator(client))

        failed = corpus.query(Adjudication).filter(Adjudication.outcome == "failed").one()
        assert failed.audit_id == "audit-refused"
        assert (failed.input_tokens, failed.output_tokens) == (500, 3)
        assert result.input_tokens == 600

    def test_a_failed_pair_is_not_asked_again_on_the_next_run(self, corpus):
        client = FakeClient(
            ModelCallFailed("boom", audit_id="a", outcome="answered"), _verdict(), _verdict()
        )
        run(corpus, ClaudeAdjudicator(client))

        second = run(corpus, ClaudeAdjudicator(client))

        assert second.asked == 0
        assert client.calls == 2

    def test_an_interrupted_run_keeps_the_answers_already_committed(self, corpus):
        client = FakeClient(_verdict(), KeyboardInterrupt())

        with pytest.raises(KeyboardInterrupt):
            run(corpus, ClaudeAdjudicator(client))
        corpus.rollback()

        assert corpus.query(Adjudication).count() == 1
        assert corpus.query(Evidence).count() == 1
        assert len(pending_pairs(corpus, PROMPT_VERSION)) == 1

    def test_an_outage_stops_the_run_with_the_pair_left_pending(self, corpus):
        outage = ModelCallFailed("APIConnectionError: down", audit_id="a", outcome="unavailable")
        client = FakeClient(_verdict(), outage)

        with pytest.raises(ModelCallFailed, match="down"):
            run(corpus, ClaudeAdjudicator(client))
        corpus.rollback()

        assert corpus.query(Adjudication).count() == 1
        assert corpus.query(Adjudication).filter(Adjudication.outcome == "failed").count() == 0
        assert len(pending_pairs(corpus, PROMPT_VERSION)) == 1

    def test_a_rejected_request_stops_the_run_with_earlier_answers_kept(self, corpus):
        rejected = ModelCallFailed("BadRequestError: bad schema", audit_id="a", outcome="rejected")
        client = FakeClient(_verdict(), rejected)

        with pytest.raises(ModelCallFailed, match="bad schema"):
            run(corpus, ClaudeAdjudicator(client))
        corpus.rollback()

        assert corpus.query(Adjudication).count() == 1
        assert corpus.query(Adjudication).filter(Adjudication.outcome == "failed").count() == 0

    def test_a_missing_key_raises_before_anything_is_written(self, corpus, memory_keyring):
        """A configuration error is not a verdict; no pair may be marked failed by it."""
        with pytest.raises(credentials.MissingCredential):
            run(corpus, ClaudeAdjudicator())

        assert corpus.query(Adjudication).count() == 0
        assert len(pending_pairs(corpus, PROMPT_VERSION)) == 2

    def test_limit_asks_only_that_many(self, corpus):
        client = FakeClient(_verdict(), _verdict())

        result = run(corpus, ClaudeAdjudicator(client), limit=1)

        assert result.asked == 1
        assert client.calls == 1


class TestDryRun:
    def test_dry_run_renders_the_text_and_writes_nothing(self, corpus):
        previews = dry_run(corpus, PROMPT_VERSION, limit=5)

        assert len(previews) == 2
        for pair, system, user, estimate in previews:
            assert system.startswith("You judge")
            assert pair.watch.claim in user
            assert estimate > 0
        assert corpus.query(Adjudication).count() == 0
