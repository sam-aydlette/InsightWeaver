"""
Tests for beat scoping on the *read* side of the commitment graph.

`brief` writes the graph; `questions`, `predictions` and `forecast` read it
back out. Scoping the write path alone is not enough -- once any beat has run,
an unscoped ledger command silently mixes that beat's questions and
predictions into what the user reads as their own. These tests pin the
boundary from the reader's side.

The load-bearing case, and the reason this file exists: with a beat run
recorded, a default-scope ledger command must not surface that beat's
questions or predictions.

Seeding helpers are reused from tests/context/test_beat_scope.py rather than
copied, so both sides of the boundary are exercised against one definition of
what "a beat run" means.

Added 2026-08-26 for backlog task 004 (read-side scoping repair).
"""

from contextlib import contextmanager

import pytest
from sqlalchemy.orm import sessionmaker

from src.cli.forecast import forecast_command
from src.cli.predictions import predictions_command
from src.cli.questions import questions_command
from src.database.models import (
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    Prediction,
)
from tests.context.test_beat_scope import (
    add_question,
    add_synthesis,
    attribute,
    ensure_beat,
    make_beat_config,
)

# Text markers unique to each scope, so an assertion can tell exactly which
# ledger produced a line of output.
BEAT_QUESTION = "Will the CUI rule take effect?"
DEFAULT_QUESTION = "Will the school board reverse itself?"
BEAT_OBSERVABLE = "CUI-RULE-OBSERVABLE"
DEFAULT_OBSERVABLE = "SCHOOL-BOARD-OBSERVABLE"
BEAT_TRIGGERED = "CUI-RULE-TRIGGERED"
DEFAULT_TRIGGERED = "SCHOOL-BOARD-TRIGGERED"

BEAT_NAME = "compliance"


def add_prediction(session, question, synthesis, observable, status):
    from src.utils import utcnow

    prediction = Prediction(
        question_id=question.id,
        observable_text=observable,
        trigger_condition="something happens",
        made_in_synthesis_id=synthesis.id,
        status=status,
        resolved_at=utcnow() if status != PREDICTION_STATUS_OPEN else None,
    )
    session.add(prediction)
    session.flush()
    return prediction


@pytest.fixture
def two_ledgers(test_engine, monkeypatch):
    """
    A database holding one beat run and one default run, each with a question,
    an open prediction and a triggered prediction.

    Every ledger command is pointed at it, so nothing here depends on whatever
    DATABASE_URL happens to name.
    """
    Session = sessionmaker(bind=test_engine)
    session = Session()

    beat_id = ensure_beat(session, make_beat_config(BEAT_NAME))

    beat_run, beat_synthesis = add_synthesis(session)
    attribute(session, beat_synthesis, beat_run, beat_id)
    beat_question = add_question(session, BEAT_QUESTION, beat_synthesis)
    add_prediction(session, beat_question, beat_synthesis, BEAT_OBSERVABLE, PREDICTION_STATUS_OPEN)
    add_prediction(
        session, beat_question, beat_synthesis, BEAT_TRIGGERED, PREDICTION_STATUS_TRIGGERED
    )

    _, default_synthesis = add_synthesis(session)
    default_question = add_question(session, DEFAULT_QUESTION, default_synthesis)
    add_prediction(
        session,
        default_question,
        default_synthesis,
        DEFAULT_OBSERVABLE,
        PREDICTION_STATUS_OPEN,
    )
    add_prediction(
        session,
        default_question,
        default_synthesis,
        DEFAULT_TRIGGERED,
        PREDICTION_STATUS_TRIGGERED,
    )
    # Ids are read out while the session is still open; the ORM objects
    # themselves must not escape it.
    ids = {
        "beat_id": beat_id,
        "beat_question_id": beat_question.id,
        "default_question_id": default_question.id,
    }
    session.commit()
    session.close()

    @contextmanager
    def _get_db():
        db = Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    for module in ("questions", "predictions", "forecast"):
        monkeypatch.setattr(f"src.cli.{module}.get_db", _get_db)

    return ids


def run(cli_runner, command, args):
    result = cli_runner.invoke(command, args)
    assert result.exit_code == 0, result.output
    return result.output


class TestDefaultScopeExcludesBeatRows:
    """
    The finding this repair pass exists for. Each of these would have passed
    trivially before any beat ran; they only bite once a beat run is recorded.
    """

    def test_questions_list_excludes_beat_questions(self, cli_runner, two_ledgers):
        output = run(cli_runner, questions_command, ["list"])

        assert DEFAULT_QUESTION in output
        assert BEAT_QUESTION not in output

    def test_predictions_open_excludes_beat_predictions(self, cli_runner, two_ledgers):
        output = run(cli_runner, predictions_command, ["open"])

        assert DEFAULT_OBSERVABLE in output
        assert BEAT_OBSERVABLE not in output

    def test_predictions_triggered_excludes_beat_predictions(self, cli_runner, two_ledgers):
        output = run(cli_runner, predictions_command, ["triggered"])

        assert DEFAULT_TRIGGERED in output
        assert BEAT_TRIGGERED not in output

    def test_forecast_excludes_beat_predictions(self, cli_runner, two_ledgers):
        output = run(cli_runner, forecast_command, [])

        assert DEFAULT_OBSERVABLE in output
        assert DEFAULT_TRIGGERED in output
        assert BEAT_OBSERVABLE not in output
        assert BEAT_TRIGGERED not in output

    def test_track_record_counts_only_your_own_predictions(self, cli_runner, two_ledgers):
        """
        The calibration number is the one figure that must never be polluted:
        four predictions exist, but only the two in this scope may be counted.
        """
        output = run(cli_runner, predictions_command, ["track-record"])

        assert "Predictions made:     2" in output


class TestBeatScopeShowsOnlyTheBeat:
    def test_questions_list_beat(self, cli_runner, two_ledgers):
        output = run(cli_runner, questions_command, ["list", "--beat", BEAT_NAME])

        assert BEAT_QUESTION in output
        assert DEFAULT_QUESTION not in output

    def test_predictions_open_beat(self, cli_runner, two_ledgers):
        output = run(cli_runner, predictions_command, ["open", "--beat", BEAT_NAME])

        assert BEAT_OBSERVABLE in output
        assert DEFAULT_OBSERVABLE not in output

    def test_forecast_beat(self, cli_runner, two_ledgers):
        output = run(cli_runner, forecast_command, ["--beat", BEAT_NAME])

        assert BEAT_OBSERVABLE in output
        assert BEAT_TRIGGERED in output
        assert DEFAULT_OBSERVABLE not in output

    def test_track_record_beat(self, cli_runner, two_ledgers):
        output = run(cli_runner, predictions_command, ["track-record", "--beat", BEAT_NAME])

        assert "Predictions made:     2" in output


class TestScopeIsVisibleInOutput:
    """A reader must be able to tell which ledger they are looking at."""

    def test_default_headings_name_your_ledger(self, cli_runner, two_ledgers):
        assert "your ledger" in run(cli_runner, questions_command, ["list"])
        assert "your ledger" in run(cli_runner, predictions_command, ["open"])
        assert "your ledger" in run(cli_runner, forecast_command, [])

    def test_beat_headings_name_the_beat(self, cli_runner, two_ledgers):
        for command, args in (
            (questions_command, ["list", "--beat", BEAT_NAME]),
            (predictions_command, ["open", "--beat", BEAT_NAME]),
            (forecast_command, ["--beat", BEAT_NAME]),
        ):
            assert f"beat '{BEAT_NAME}'" in run(cli_runner, command, args)


class TestUnknownBeatIsAnErrorNotAnEmptyLedger:
    """
    An empty result would read as "you have nothing here", which is a wrong
    answer rather than a missing one.
    """

    @pytest.mark.parametrize(
        ("command", "args"),
        [
            (questions_command, ["list", "--beat", "nope"]),
            (predictions_command, ["open", "--beat", "nope"]),
            (predictions_command, ["track-record", "--beat", "nope"]),
            (forecast_command, ["--beat", "nope"]),
        ],
    )
    def test_names_the_beats_that_have_run(self, cli_runner, two_ledgers, command, args):
        result = cli_runner.invoke(command, args)

        assert result.exit_code != 0
        assert "No beat named 'nope'" in result.output
        assert BEAT_NAME in result.output


class TestIdAddressedCommandsStayGlobalAndDisclose:
    """
    `questions show` and `questions resolve` name a specific row, so they are
    deliberately not scoped -- but they say which ledger the row belongs to,
    so the choice is visible rather than silent.
    """

    def test_show_finds_a_beat_question_from_the_default_context(self, cli_runner, two_ledgers):
        output = run(cli_runner, questions_command, ["show", str(two_ledgers["beat_question_id"])])

        assert BEAT_QUESTION in output
        assert f"Ledger: {BEAT_NAME}" in output

    def test_show_discloses_the_default_ledger_too(self, cli_runner, two_ledgers):
        output = run(
            cli_runner, questions_command, ["show", str(two_ledgers["default_question_id"])]
        )

        assert DEFAULT_QUESTION in output
        assert "Ledger: yours (no beat)" in output

    def test_resolve_reports_the_ledger_it_touched(self, cli_runner, two_ledgers):
        output = run(
            cli_runner,
            questions_command,
            [
                "resolve",
                str(two_ledgers["beat_question_id"]),
                "--note",
                "the rule took effect",
            ],
        )

        assert f"resolved in beat {BEAT_NAME}" in output


class TestUnmigratedDatabaseReadsUnchanged:
    """
    On a database that predates beats the ledger commands must behave exactly
    as they always have -- that is what makes this repair safe to ship to an
    existing install.
    """

    @pytest.fixture
    def pre_beat_ledger(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine

        from src.database.models import Base

        engine = create_engine(f"sqlite:///{tmp_path / 'pre-beat.db'}")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                table
                for name, table in Base.metadata.tables.items()
                if name not in ("beats", "beat_runs")
            ],
        )
        Session = sessionmaker(bind=engine)
        session = Session()
        _, synthesis = add_synthesis(session)
        question = add_question(session, DEFAULT_QUESTION, synthesis)
        add_prediction(session, question, synthesis, DEFAULT_OBSERVABLE, PREDICTION_STATUS_OPEN)
        session.commit()
        session.close()

        @contextmanager
        def _get_db():
            db = Session()
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        for module in ("questions", "predictions", "forecast"):
            monkeypatch.setattr(f"src.cli.{module}.get_db", _get_db)

    def test_questions_list_still_works(self, cli_runner, pre_beat_ledger):
        assert DEFAULT_QUESTION in run(cli_runner, questions_command, ["list"])

    def test_predictions_open_still_works(self, cli_runner, pre_beat_ledger):
        assert DEFAULT_OBSERVABLE in run(cli_runner, predictions_command, ["open"])

    def test_forecast_still_works(self, cli_runner, pre_beat_ledger):
        assert DEFAULT_OBSERVABLE in run(cli_runner, forecast_command, [])

    def test_beat_flag_is_refused_with_the_migration_command(self, cli_runner, pre_beat_ledger):
        result = cli_runner.invoke(questions_command, ["list", "--beat", BEAT_NAME])

        assert result.exit_code != 0
        assert "add_beats" in result.output
