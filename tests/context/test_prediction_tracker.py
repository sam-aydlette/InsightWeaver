"""
Tests for the prediction tracker and the synthesizer's prediction extraction.
"""

import json
from datetime import datetime, timedelta

import pytest

from src.context.prediction_tracker import PredictionTracker
from src.context.synthesizer import NarrativeSynthesizer
from src.database.models import (
    PREDICTION_EXPIRY_DAYS,
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_EXPIRED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    QUESTION_STATUS_OPEN,
    AnalysisRun,
    NarrativeSynthesis,
    Prediction,
    Question,
)


def _make_synthesis(session):
    run = AnalysisRun(run_type="situation_synthesis", status="completed")
    session.add(run)
    session.flush()
    synth = NarrativeSynthesis(analysis_run_id=run.id)
    session.add(synth)
    session.flush()
    return synth


def _make_prediction(session, synth, question, observable="Fed cuts rates", made_at=None):
    pred = Prediction(
        question_id=question.id,
        observable_text=observable,
        trigger_condition="Fed announces a cut at the next meeting",
        made_in_synthesis_id=synth.id,
        status=PREDICTION_STATUS_OPEN,
    )
    if made_at:
        pred.made_at = made_at
    session.add(pred)
    session.flush()
    return pred


class TestPredictionTracker:
    @pytest.fixture
    def tracker(self, mock_claude_client):
        return PredictionTracker(client=mock_claude_client)

    @pytest.mark.asyncio
    async def test_no_predictions_returns_zero_summary(self, tracker, test_session):
        summary = await tracker.check_open_predictions([{"title": "x"}], test_session)
        assert summary["checked"] == 0
        assert summary["triggered"] == 0
        assert summary["expired"] == 0

    @pytest.mark.asyncio
    async def test_expires_stale_predictions(self, tracker, test_session, mock_claude_client):
        q = Question(text="Q?", normalized_text="q", status=QUESTION_STATUS_OPEN)
        test_session.add(q)
        test_session.flush()
        synth = _make_synthesis(test_session)
        old = _make_prediction(
            test_session,
            synth,
            q,
            made_at=datetime.utcnow() - timedelta(days=PREDICTION_EXPIRY_DAYS + 5),
        )
        test_session.commit()

        # No articles -> LLM not called, but expiry still runs.
        summary = await tracker.check_open_predictions([], test_session)
        test_session.commit()

        test_session.refresh(old)
        assert old.status == PREDICTION_STATUS_EXPIRED
        assert old.resolved_at is not None
        assert summary["expired"] == 1
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_triggered_verdict_resolves_prediction(
        self, tracker, test_session, mock_claude_client
    ):
        q = Question(
            text="Will the Fed cut?",
            normalized_text="will the fed cut",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(q)
        test_session.flush()
        synth = _make_synthesis(test_session)
        pred = _make_prediction(test_session, synth, q)
        test_session.commit()

        mock_claude_client.analyze.return_value = json.dumps(
            {
                "verdicts": [
                    {"prediction_id": pred.id, "verdict": "triggered", "note": "Fed cut reported."}
                ]
            }
        )

        summary = await tracker.check_open_predictions(
            [{"title": "Fed cuts rates", "content": "The Fed announced a cut."}], test_session
        )
        test_session.commit()

        test_session.refresh(pred)
        assert pred.status == PREDICTION_STATUS_TRIGGERED
        assert pred.resolution_note.startswith("Triggered:")
        assert summary["triggered"] == 1
        assert summary["still_open"] == 0

    @pytest.mark.asyncio
    async def test_contradicted_verdict_resolves_prediction(
        self, tracker, test_session, mock_claude_client
    ):
        q = Question(
            text="Will the Fed cut?",
            normalized_text="will the fed cut",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(q)
        test_session.flush()
        synth = _make_synthesis(test_session)
        pred = _make_prediction(test_session, synth, q)
        test_session.commit()

        mock_claude_client.analyze.return_value = json.dumps(
            {
                "verdicts": [
                    {
                        "prediction_id": pred.id,
                        "verdict": "contradicted",
                        "note": "Fed official ruled out a cut.",
                    }
                ]
            }
        )

        summary = await tracker.check_open_predictions(
            [{"title": "No cut coming", "content": "A Fed official ruled it out."}], test_session
        )
        test_session.commit()

        test_session.refresh(pred)
        assert pred.status == PREDICTION_STATUS_CONTRADICTED
        assert summary["contradicted"] == 1

    @pytest.mark.asyncio
    async def test_open_verdict_leaves_prediction_open(
        self, tracker, test_session, mock_claude_client
    ):
        q = Question(
            text="Will the Fed cut?",
            normalized_text="will the fed cut",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(q)
        test_session.flush()
        synth = _make_synthesis(test_session)
        pred = _make_prediction(test_session, synth, q)
        test_session.commit()

        mock_claude_client.analyze.return_value = json.dumps(
            {"verdicts": [{"prediction_id": pred.id, "verdict": "open", "note": "No bearing."}]}
        )

        summary = await tracker.check_open_predictions(
            [{"title": "Unrelated news", "content": "Something else."}], test_session
        )
        test_session.commit()

        test_session.refresh(pred)
        assert pred.status == PREDICTION_STATUS_OPEN
        assert summary["still_open"] == 1

    @pytest.mark.asyncio
    async def test_llm_failure_leaves_predictions_open(
        self, tracker, test_session, mock_claude_client
    ):
        q = Question(text="Q?", normalized_text="q", status=QUESTION_STATUS_OPEN)
        test_session.add(q)
        test_session.flush()
        synth = _make_synthesis(test_session)
        pred = _make_prediction(test_session, synth, q)
        test_session.commit()

        mock_claude_client.analyze.side_effect = RuntimeError("API down")

        summary = await tracker.check_open_predictions(
            [{"title": "News", "content": "..."}], test_session
        )
        test_session.commit()

        test_session.refresh(pred)
        assert pred.status == PREDICTION_STATUS_OPEN
        assert summary["still_open"] == 1


class TestCollectPredictions:
    def test_collect_list_shape(self):
        situations = [
            {
                "where_this_goes": {
                    "what_to_watch": [
                        {"observable": "Fed cuts", "trigger_condition": "cut announced"},
                        {"observable": "Yield inverts", "trigger_condition": "2y > 10y"},
                    ]
                }
            },
            {"where_this_goes": {"what_to_watch": []}},
        ]
        out = NarrativeSynthesizer._collect_predictions(situations)
        assert out == [
            (0, "Fed cuts", "cut announced"),
            (0, "Yield inverts", "2y > 10y"),
        ]

    def test_collect_skips_incomplete_entries(self):
        situations = [
            {
                "where_this_goes": {
                    "what_to_watch": [
                        {"observable": "Has observable but no trigger"},
                        {"trigger_condition": "Has trigger but no observable"},
                        "a bare string",
                    ]
                }
            }
        ]
        assert NarrativeSynthesizer._collect_predictions(situations) == []

    def test_collect_handles_missing_futures(self):
        assert NarrativeSynthesizer._collect_predictions([{}, {"where_this_goes": {}}]) == []
