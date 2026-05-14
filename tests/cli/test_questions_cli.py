"""
Tests for the `questions` CLI command.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.cli.questions import questions_command
from src.database.models import (
    QUESTION_STATUS_OPEN,
    QUESTION_STATUS_RESOLVED,
    AnalysisRun,
    NarrativeSynthesis,
    Question,
    QuestionSituation,
)


@pytest.fixture
def populated_session(test_session):
    """Seed a session with a handful of questions, syntheses, and join rows."""
    open_q = Question(
        text="Will the Fed cut rates in June?",
        normalized_text="will the fed cut rates in june",
        first_asked_at=datetime.utcnow() - timedelta(days=20),
        status=QUESTION_STATUS_OPEN,
    )
    resolved_q = Question(
        text="Did the bill pass?",
        normalized_text="did the bill pass",
        first_asked_at=datetime.utcnow() - timedelta(days=60),
        resolved_at=datetime.utcnow() - timedelta(days=5),
        resolution_note="Passed on third reading.",
        status=QUESTION_STATUS_RESOLVED,
    )
    test_session.add_all([open_q, resolved_q])
    test_session.flush()

    run = AnalysisRun(run_type="situation_synthesis", status="completed")
    test_session.add(run)
    test_session.flush()
    synth = NarrativeSynthesis(
        analysis_run_id=run.id,
        synthesis_data={"situations": [{"title": "Fed June meeting watch"}]},
    )
    test_session.add(synth)
    test_session.flush()

    test_session.add(
        QuestionSituation(question_id=open_q.id, synthesis_id=synth.id, situation_index=0)
    )
    test_session.commit()
    return test_session, open_q, resolved_q, synth


def _patch_db(session, target):
    """Patch get_db so the CLI subcommand reuses the test session.

    The CLI commits inside the context; we want changes to persist but the
    session itself to stay open so the test can re-query.
    """
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    return patch(target, _ctx)


class TestList:
    def test_lists_open_questions(self, cli_runner, populated_session):
        session, open_q, _, _ = populated_session
        with _patch_db(session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(questions_command, ["list"])

        assert result.exit_code == 0
        assert f"Q{open_q.id}" in result.output
        assert "Will the Fed cut rates in June?" in result.output
        assert "Did the bill pass?" not in result.output

    def test_lists_resolved_when_requested(self, cli_runner, populated_session):
        session, _, resolved_q, _ = populated_session
        with _patch_db(session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(questions_command, ["list", "-s", "resolved"])

        assert result.exit_code == 0
        assert f"Q{resolved_q.id}" in result.output

    def test_empty_status_message(self, cli_runner, test_session):
        with _patch_db(test_session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(questions_command, ["list"])

        assert result.exit_code == 0
        assert "No open questions" in result.output


class TestShow:
    def test_shows_question_and_appearances(self, cli_runner, populated_session):
        session, open_q, _, synth = populated_session
        with _patch_db(session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(questions_command, ["show", str(open_q.id)])

        assert result.exit_code == 0
        assert f"Q{open_q.id}" in result.output
        assert "Will the Fed cut rates in June?" in result.output
        assert "Fed June meeting watch" in result.output

    def test_unknown_question(self, cli_runner, test_session):
        with _patch_db(test_session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(questions_command, ["show", "9999"])

        assert result.exit_code == 0
        assert "not found" in result.output


class TestResolve:
    def test_resolve_open_question(self, cli_runner, populated_session):
        session, open_q, _, _ = populated_session
        with _patch_db(session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(
                questions_command,
                ["resolve", str(open_q.id), "--note", "Fed cut as expected."],
            )

        assert result.exit_code == 0
        assert "resolved" in result.output
        session.refresh(open_q)
        assert open_q.status == QUESTION_STATUS_RESOLVED
        assert open_q.resolution_note == "Fed cut as expected."

    def test_cannot_resolve_already_resolved(self, cli_runner, populated_session):
        session, _, resolved_q, _ = populated_session
        with _patch_db(session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(
                questions_command,
                ["resolve", str(resolved_q.id), "--note", "..."],
            )

        assert result.exit_code == 0
        assert "already resolved" in result.output

    def test_cannot_resolve_missing(self, cli_runner, test_session):
        with _patch_db(test_session, "src.cli.questions.get_db"):
            result = cli_runner.invoke(questions_command, ["resolve", "9999", "--note", "..."])

        assert result.exit_code == 0
        assert "not found" in result.output
