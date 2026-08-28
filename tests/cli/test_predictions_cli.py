"""
Tests for the `predictions` CLI command.
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest

from src.cli.predictions import predictions_command
from src.database.models import (
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    AnalysisRun,
    NarrativeSynthesis,
    Prediction,
    Question,
)


def _patch_db(session):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    return patch("src.cli.predictions.get_db", _ctx)


@pytest.fixture
def populated_session(test_session):
    q = Question(text="Will the Fed cut?", normalized_text="will the fed cut", status="open")
    test_session.add(q)
    test_session.flush()
    run = AnalysisRun(run_type="situation_synthesis", status="completed")
    test_session.add(run)
    test_session.flush()
    synth = NarrativeSynthesis(analysis_run_id=run.id)
    test_session.add(synth)
    test_session.flush()

    open_p = Prediction(
        question_id=q.id,
        observable_text="Fed announces a cut",
        trigger_condition="rate decision at next meeting",
        made_in_synthesis_id=synth.id,
        status=PREDICTION_STATUS_OPEN,
    )
    triggered_p = Prediction(
        question_id=q.id,
        observable_text="CPI prints below 3%",
        trigger_condition="May CPI release",
        made_in_synthesis_id=synth.id,
        status=PREDICTION_STATUS_TRIGGERED,
        resolved_at=datetime.utcnow(),
        resolution_note="Triggered: CPI came in at 2.8%.",
    )
    contradicted_p = Prediction(
        question_id=q.id,
        observable_text="Layoffs accelerate",
        trigger_condition="weekly claims spike",
        made_in_synthesis_id=synth.id,
        status=PREDICTION_STATUS_CONTRADICTED,
        resolved_at=datetime.utcnow(),
        resolution_note="Contradicted: claims fell.",
    )
    test_session.add_all([open_p, triggered_p, contradicted_p])
    test_session.commit()
    return test_session, open_p, triggered_p, contradicted_p


class TestOpen:
    def test_lists_open(self, cli_runner, populated_session):
        session, open_p, _, _ = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(predictions_command, ["open"])
        assert result.exit_code == 0
        assert f"P{open_p.id}" in result.output
        assert "Fed announces a cut" in result.output
        assert "CPI prints below 3%" not in result.output

    def test_empty(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(predictions_command, ["open"])
        assert result.exit_code == 0
        assert "No open predictions" in result.output


class TestTriggered:
    def test_lists_triggered_with_resolution(self, cli_runner, populated_session):
        session, _, triggered_p, _ = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(predictions_command, ["triggered"])
        assert result.exit_code == 0
        assert f"P{triggered_p.id}" in result.output
        assert "CPI came in at 2.8%" in result.output


class TestContradicted:
    def test_lists_contradicted(self, cli_runner, populated_session):
        session, _, _, contradicted_p = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(predictions_command, ["contradicted"])
        assert result.exit_code == 0
        assert f"P{contradicted_p.id}" in result.output
        assert "claims fell" in result.output


class TestTrackRecord:
    def test_track_record_summary(self, cli_runner, populated_session):
        """
        The fixture's predictions are all model-authored, so they are reported
        under the model heading and produce no hit rate. Backlog task 011
        moved the calibration figure to operator predictions only: a track
        record that blends the two measures nothing.
        """
        session, _, _, _ = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(predictions_command, ["track-record"])
        assert result.exit_code == 0
        assert "MODEL PREDICTIONS (not counted toward your calibration)" in result.output
        assert "3 made | 1 triggered | 1 contradicted | 1 open" in result.output
        assert "You have staked nothing in this window" in result.output
        assert "Hit rate" not in result.output

    def test_track_record_empty_window(self, cli_runner, populated_session):
        session, _, _, _ = populated_session
        # Window of 0 days excludes everything made "today or earlier".
        with _patch_db(session):
            result = cli_runner.invoke(predictions_command, ["track-record", "--days", "0"])
        assert result.exit_code == 0
        # Either no predictions in window or none resolved -- both are valid empties.
        assert "No predictions" in result.output or "No predictions made" in result.output
