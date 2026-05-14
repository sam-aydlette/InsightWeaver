"""
Tests for the question matcher and synthesizer helpers that resolve
unresolved_questions into the persistent Question graph.
"""

import json
from datetime import datetime, timedelta

import pytest

from src.context.question_matcher import (
    ProposedQuestion,
    QuestionMatcher,
    normalize_question,
)
from src.context.synthesizer import NarrativeSynthesizer
from src.database.models import (
    QUESTION_STATUS_OPEN,
    QUESTION_STATUS_RESOLVED,
    Question,
    QuestionSituation,
)


class TestNormalize:
    def test_lowercases(self):
        assert normalize_question("Will The Fed Cut?") == "will the fed cut"

    def test_strips_punctuation(self):
        assert normalize_question("Will the Fed cut rates?!") == "will the fed cut rates"

    def test_collapses_whitespace(self):
        assert normalize_question("  Will   the\tFed  cut?  ") == "will the fed cut"

    def test_handles_unicode(self):
        # diacritics get folded
        assert normalize_question("Café opens?") == "cafe opens"

    def test_empty_text(self):
        assert normalize_question("") == ""
        assert normalize_question(None) == ""


class TestQuestionMatcher:
    @pytest.fixture
    def matcher(self, mock_claude_client):
        return QuestionMatcher(client=mock_claude_client)

    @pytest.mark.asyncio
    async def test_empty_proposed_returns_empty(self, matcher, test_session):
        result = await matcher.resolve_questions([], test_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_creates_new_when_no_existing(self, matcher, test_session, mock_claude_client):
        proposed = [ProposedQuestion("Will the Fed cut?", is_primary=True)]
        # No open questions exist, so LLM should not be called.
        result = await matcher.resolve_questions(proposed, test_session)
        test_session.commit()

        assert len(result) == 1
        assert result[0].id is not None
        assert result[0].text == "Will the Fed cut?"
        assert result[0].normalized_text == "will the fed cut"
        assert result[0].status == QUESTION_STATUS_OPEN
        assert result[0].is_primary is True
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_exact_normalized_match_short_circuits_llm(
        self, matcher, test_session, mock_claude_client
    ):
        existing = Question(
            text="Will the Fed cut rates?",
            normalized_text="will the fed cut rates",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(existing)
        test_session.commit()

        proposed = [ProposedQuestion("Will the Fed cut rates?", is_primary=True)]
        result = await matcher.resolve_questions(proposed, test_session)
        test_session.commit()

        assert result[0].id == existing.id
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_match_path(self, matcher, test_session, mock_claude_client):
        existing = Question(
            text="Will the Fed cut rates in June?",
            normalized_text="will the fed cut rates in june",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(existing)
        test_session.commit()

        # Different phrasing, so exact match fails; LLM says it matches existing.
        mock_claude_client.analyze.return_value = json.dumps(
            {"matches": [{"proposed_index": 0, "matched_id": existing.id, "reasoning": "same"}]}
        )

        proposed = [ProposedQuestion("Does the Fed pivot at the June meeting?", is_primary=True)]
        result = await matcher.resolve_questions(proposed, test_session)
        test_session.commit()

        assert result[0].id == existing.id
        mock_claude_client.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_says_new_creates_new(self, matcher, test_session, mock_claude_client):
        existing = Question(
            text="Will the Fed cut rates?",
            normalized_text="will the fed cut rates",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(existing)
        test_session.commit()

        mock_claude_client.analyze.return_value = json.dumps(
            {"matches": [{"proposed_index": 0, "matched_id": None, "reasoning": "unrelated"}]}
        )

        proposed = [ProposedQuestion("Will inflation come down?", is_primary=False)]
        result = await matcher.resolve_questions(proposed, test_session)
        test_session.commit()

        assert result[0].id != existing.id
        assert result[0].text == "Will inflation come down?"
        assert result[0].is_primary is False
        assert result[0].previous_question_id is None

    @pytest.mark.asyncio
    async def test_previous_question_link_from_resolved(
        self, matcher, test_session, mock_claude_client
    ):
        resolved = Question(
            text="Will the Fed cut in March?",
            normalized_text="will the fed cut in march",
            status=QUESTION_STATUS_RESOLVED,
            resolved_at=datetime.utcnow() - timedelta(days=30),
            resolution_note="Cut happened.",
        )
        test_session.add(resolved)
        test_session.commit()

        proposed = [ProposedQuestion("Will the Fed cut in March?", is_primary=True)]
        result = await matcher.resolve_questions(proposed, test_session)
        test_session.commit()

        # New Question created with link back to the resolved one (no auto-reopen).
        assert result[0].id != resolved.id
        assert result[0].status == QUESTION_STATUS_OPEN
        assert result[0].previous_question_id == resolved.id

    @pytest.mark.asyncio
    async def test_llm_failure_treats_all_as_new(self, matcher, test_session, mock_claude_client):
        existing = Question(
            text="Will the Fed cut rates?",
            normalized_text="will the fed cut rates",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(existing)
        test_session.commit()

        mock_claude_client.analyze.side_effect = RuntimeError("API down")

        proposed = [ProposedQuestion("Does the Fed pivot at the June meeting?", is_primary=True)]
        result = await matcher.resolve_questions(proposed, test_session)
        test_session.commit()

        # LLM failed; matcher fell back to creating a new question.
        assert result[0].id != existing.id
        assert result[0].text.startswith("Does the Fed pivot")


class TestSynthesizerCollectAndEnrich:
    def test_collect_new_shape(self):
        situations = [
            {
                "where_this_goes": {
                    "unresolved_questions": {
                        "primary": "Will A?",
                        "secondary": ["Will B?", "Will C?"],
                    }
                }
            },
            {"where_this_goes": {"unresolved_questions": {"primary": "Will D?", "secondary": []}}},
        ]
        plan = NarrativeSynthesizer._collect_proposed_questions(situations)
        assert len(plan) == 4
        assert plan[0] == (0, "primary", ProposedQuestion("Will A?", True))
        assert plan[1] == (0, "secondary:0", ProposedQuestion("Will B?", False))
        assert plan[2] == (0, "secondary:1", ProposedQuestion("Will C?", False))
        assert plan[3] == (1, "primary", ProposedQuestion("Will D?", True))

    def test_collect_legacy_string_shape(self):
        situations = [
            {"where_this_goes": {"unresolved_question": "Will Z?"}},
        ]
        plan = NarrativeSynthesizer._collect_proposed_questions(situations)
        assert len(plan) == 1
        assert plan[0] == (0, "primary", ProposedQuestion("Will Z?", True))

    def test_collect_skips_empty(self):
        situations = [
            {"where_this_goes": {"unresolved_questions": {"primary": "", "secondary": [""]}}},
            {"where_this_goes": {}},
            {},
        ]
        plan = NarrativeSynthesizer._collect_proposed_questions(situations)
        assert plan == []

    def test_enrich_attaches_metadata(self, test_session):
        # Build a resolved-Question structure manually to mimic the matcher.
        q1 = Question(
            text="Will A?",
            normalized_text="will a",
            first_asked_at=datetime(2026, 3, 12, 10, 0, 0),
            status=QUESTION_STATUS_OPEN,
        )
        q2 = Question(
            text="Will B?",
            normalized_text="will b",
            first_asked_at=datetime(2026, 5, 1, 8, 0, 0),
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add_all([q1, q2])
        test_session.commit()

        situations = [
            {
                "where_this_goes": {
                    "unresolved_questions": {"primary": "Will A?", "secondary": ["Will B?"]}
                }
            }
        ]
        plan = [
            (0, "primary", ProposedQuestion("Will A?", True)),
            (0, "secondary:0", ProposedQuestion("Will B?", False)),
        ]

        NarrativeSynthesizer._enrich_situations_with_questions(situations, plan, [q1, q2])
        enriched = situations[0]["where_this_goes"]["unresolved_questions"]
        assert enriched["primary"]["text"] == "Will A?"
        assert enriched["primary"]["question_id"] == q1.id
        assert enriched["primary"]["first_asked_at"] == "2026-03-12T10:00:00"
        assert enriched["primary"]["appearance_count"] == 1
        assert len(enriched["secondary"]) == 1
        assert enriched["secondary"][0]["question_id"] == q2.id
        assert "unresolved_question" not in situations[0]["where_this_goes"]


class TestQuestionSituationConstraint:
    """The unique constraint protects against double-writing the same join row."""

    def test_unique_constraint_blocks_duplicates(self, test_session):
        from sqlalchemy.exc import IntegrityError

        from src.database.models import AnalysisRun, NarrativeSynthesis

        run = AnalysisRun(run_type="x", status="completed")
        test_session.add(run)
        test_session.flush()
        synth = NarrativeSynthesis(analysis_run_id=run.id)
        test_session.add(synth)
        test_session.flush()

        q = Question(text="Q?", normalized_text="q", status=QUESTION_STATUS_OPEN)
        test_session.add(q)
        test_session.flush()

        test_session.add(
            QuestionSituation(question_id=q.id, synthesis_id=synth.id, situation_index=0)
        )
        test_session.commit()

        test_session.add(
            QuestionSituation(question_id=q.id, synthesis_id=synth.id, situation_index=0)
        )
        with pytest.raises(IntegrityError):
            test_session.commit()
