"""
Tests for the operator calibration loop (backlog task 011).

The finding this feature answers: the tool generated 33 predictions and graded
zero, because 25 were phrased "X would signal Y" and only 3 carried a date. The
tests that matter most here are therefore the refusals -- a claim with no date
must not reach the database at all.
"""

import socket
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

import pytest

from src.cli.forecast import forecast_command
from src.cli.predictions import predictions_command
from src.cli.questions import questions_command
from src.cli.stake import predict_command, resolve_command
from src.database.models import (
    PREDICTION_AUTHOR_MODEL,
    PREDICTION_AUTHOR_OPERATOR,
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    QUESTION_STATUS_OPEN,
    AnalysisRun,
    NarrativeSynthesis,
    Prediction,
    Question,
)
from src.utils import utcnow

# Every command that touches the loop reads the database through its own
# module's get_db, so all of them are redirected at once.
_DB_TARGETS = (
    "src.cli.questions.get_db",
    "src.cli.stake.get_db",
    "src.cli.forecast.get_db",
    "src.cli.predictions.get_db",
)


@contextmanager
def use_session(session):
    """Point every loop command at one test session."""

    @contextmanager
    def _ctx():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    with (
        patch(_DB_TARGETS[0], _ctx),
        patch(_DB_TARGETS[1], _ctx),
        patch(_DB_TARGETS[2], _ctx),
        patch(_DB_TARGETS[3], _ctx),
    ):
        yield


def run(cli_runner, session, command, args):
    with use_session(session):
        return cli_runner.invoke(command, args)


def make_question(session, text, cadence, *, first_asked_days_ago=0, last_reviewed_days_ago=None):
    q = Question(
        text=text,
        normalized_text=text.lower(),
        first_asked_at=utcnow() - timedelta(days=first_asked_days_ago),
        status=QUESTION_STATUS_OPEN,
        cadence=cadence,
        last_reviewed_at=(
            None
            if last_reviewed_days_ago is None
            else utcnow() - timedelta(days=last_reviewed_days_ago)
        ),
    )
    session.add(q)
    session.commit()
    return q


def future_date(days):
    return (utcnow() + timedelta(days=days)).date().isoformat()


class TestQuestionsAdd:
    def test_declares_a_question_at_a_cadence(self, cli_runner, test_session):
        result = run(
            cli_runner,
            test_session,
            questions_command,
            ["add", "Does CMMC Phase 2 slip past its statutory date?", "--cadence", "90d"],
        )

        assert result.exit_code == 0
        stored = test_session.query(Question).one()
        assert stored.text == "Does CMMC Phase 2 slip past its statutory date?"
        assert stored.cadence == "90d"
        # Never reviewed: the first interval counts from when it was declared.
        assert stored.last_reviewed_at is None

    def test_cadence_is_required(self, cli_runner, test_session):
        result = run(cli_runner, test_session, questions_command, ["add", "Something"])

        assert result.exit_code != 0
        assert test_session.query(Question).count() == 0

    def test_unreadable_cadence_is_refused(self, cli_runner, test_session):
        result = run(
            cli_runner, test_session, questions_command, ["add", "Something", "--cadence", "soon"]
        )

        assert result.exit_code != 0
        assert "not a review cadence" in result.output
        assert "Nothing was stored" in result.output
        assert test_session.query(Question).count() == 0

    def test_list_shows_cadence_and_time_until_next_review(self, cli_runner, test_session):
        make_question(test_session, "Slow question", "90d", first_asked_days_ago=10)

        result = run(cli_runner, test_session, questions_command, ["list"])

        assert result.exit_code == 0
        assert "cadence 90d" in result.output
        assert "next review in 79d" in result.output


class TestDateIsRejectedAtEntry:
    """
    The core requirement. A claim with no resolution date can never come due,
    so it can never be graded -- which is how 19 predictions expired unjudged.
    """

    def test_missing_by_is_refused_and_nothing_is_stored(self, cli_runner, test_session):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")

        result = run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--confidence", "0.7"],
        )

        assert result.exit_code != 0
        assert "--by is required" in result.output
        assert "Nothing was stored" in result.output
        assert test_session.query(Prediction).count() == 0

    def test_missing_confidence_is_refused_and_nothing_is_stored(self, cli_runner, test_session):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")

        result = run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", future_date(60)],
        )

        assert result.exit_code != 0
        assert "--confidence is required" in result.output
        assert test_session.query(Prediction).count() == 0

    def test_no_confidence_default_is_applied(self, cli_runner, test_session):
        """A stake with an unstated confidence is a non-commitment in costume."""
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")

        run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", future_date(60)],
        )

        assert test_session.query(Prediction).count() == 0

    def test_past_due_date_is_refused(self, cli_runner, test_session):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")
        past = (utcnow() - timedelta(days=1)).date().isoformat()

        result = run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", past, "--confidence", "0.7"],
        )

        assert result.exit_code != 0
        assert "is in the past" in result.output
        assert test_session.query(Prediction).count() == 0

    def test_confidence_outside_zero_to_one_is_refused(self, cli_runner, test_session):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")

        result = run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", future_date(60), "--confidence", "7"],
        )

        assert result.exit_code != 0
        assert test_session.query(Prediction).count() == 0

    def test_unknown_question_is_refused(self, cli_runner, test_session):
        result = run(
            cli_runner,
            test_session,
            predict_command,
            ["999", "Yes", "--by", future_date(30), "--confidence", "0.5"],
        )

        assert result.exit_code != 0
        assert test_session.query(Prediction).count() == 0


class TestStakingStores:
    def test_a_complete_claim_is_stored_with_author_date_and_confidence(
        self, cli_runner, test_session
    ):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")

        result = run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", "2099-12-31", "--confidence", "0.7"],
        )

        assert result.exit_code == 0
        p = test_session.query(Prediction).one()
        assert p.author == PREDICTION_AUTHOR_OPERATOR
        assert p.observable_text == "Yes -- slips"
        assert p.due_by.date().isoformat() == "2099-12-31"
        assert p.confidence == pytest.approx(0.7)
        assert p.status == PREDICTION_STATUS_OPEN
        assert p.made_in_synthesis_id is None
        assert p.outcome is None


class TestResolve:
    def _staked(self, cli_runner, test_session, days_out=30):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")
        run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", future_date(days_out), "--confidence", "0.7"],
        )
        return q, test_session.query(Prediction).one()

    def test_resolving_before_the_due_date_is_allowed_and_says_so(self, cli_runner, test_session):
        """
        The event can settle early. What matters is that the resolution date is
        recorded separately from the due date, so grading early -- or three
        months late -- is itself visible.
        """
        _, p = self._staked(cli_runner, test_session, days_out=30)

        result = run(
            cli_runner,
            test_session,
            resolve_command,
            [str(p.id), "--outcome", "no", "--note", "DFARS class deviation published."],
        )

        assert result.exit_code == 0
        assert "before it came due" in result.output
        test_session.refresh(p)
        assert p.outcome == "no"
        assert p.status == PREDICTION_STATUS_CONTRADICTED
        assert p.resolved_at is not None
        assert p.resolved_at.date() < p.due_by.date()
        assert p.resolution_note == "DFARS class deviation published."

    def test_resolving_twice_is_refused(self, cli_runner, test_session):
        _, p = self._staked(cli_runner, test_session)
        run(
            cli_runner,
            test_session,
            resolve_command,
            [str(p.id), "--outcome", "yes", "--note", "First verdict."],
        )

        result = run(
            cli_runner,
            test_session,
            resolve_command,
            [str(p.id), "--outcome", "no", "--note", "Changed my mind."],
        )

        assert result.exit_code != 0
        assert "already triggered" in result.output
        assert "not editable" in result.output
        test_session.refresh(p)
        assert p.outcome == "yes"
        assert p.status == PREDICTION_STATUS_TRIGGERED
        assert p.resolution_note == "First verdict."

    def test_note_is_required(self, cli_runner, test_session):
        _, p = self._staked(cli_runner, test_session)

        result = run(cli_runner, test_session, resolve_command, [str(p.id), "--outcome", "yes"])

        assert result.exit_code != 0
        test_session.refresh(p)
        assert p.status == PREDICTION_STATUS_OPEN

    def test_unknown_prediction_is_refused(self, cli_runner, test_session):
        result = run(
            cli_runner, test_session, resolve_command, ["999", "--outcome", "yes", "--note", "x"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output


class TestDueRespectsEachQuestionsOwnCadence:
    def test_a_question_whose_cadence_has_not_elapsed_is_absent(self, cli_runner, test_session):
        make_question(test_session, "Slow moving subject", "90d", first_asked_days_ago=10)

        result = run(cli_runner, test_session, forecast_command, ["--due"])

        assert result.exit_code == 0
        assert "Slow moving subject" not in result.output
        assert "QUESTIONS DUE FOR REVIEW (0)" in result.output

    def test_two_cadences_come_due_independently(self, cli_runner, test_session):
        """
        The whole point of a per-question interval: at ten days elapsed the
        weekly question is due and the quarterly one is not.
        """
        fast = make_question(test_session, "Fast moving subject", "7d", first_asked_days_ago=10)
        slow = make_question(test_session, "Slow moving subject", "90d", first_asked_days_ago=10)

        result = run(cli_runner, test_session, forecast_command, ["--due"])

        assert result.exit_code == 0
        assert "Fast moving subject" in result.output
        assert "Slow moving subject" not in result.output
        assert "QUESTIONS DUE FOR REVIEW (1)" in result.output

        test_session.refresh(fast)
        test_session.refresh(slow)
        assert fast.last_reviewed_at is not None
        assert slow.last_reviewed_at is None

    def test_the_slow_one_comes_due_on_its_own_schedule(self, cli_runner, test_session):
        make_question(test_session, "Fast moving subject", "7d", first_asked_days_ago=100)
        make_question(test_session, "Slow moving subject", "90d", first_asked_days_ago=100)

        result = run(cli_runner, test_session, forecast_command, ["--due"])

        assert "Fast moving subject" in result.output
        assert "Slow moving subject" in result.output
        assert "QUESTIONS DUE FOR REVIEW (2)" in result.output

    def test_reviewing_stamps_even_when_nothing_moved(self, cli_runner, test_session):
        q = make_question(test_session, "Quiet question", "7d", first_asked_days_ago=10)

        first = run(cli_runner, test_session, forecast_command, ["--due"])
        assert "Quiet question" in first.output
        assert "Stamped as reviewed: Q" in first.output

        second = run(cli_runner, test_session, forecast_command, ["--due"])
        assert "Quiet question" not in second.output
        assert "QUESTIONS DUE FOR REVIEW (0)" in second.output

        test_session.refresh(q)
        assert q.last_reviewed_at is not None

    def test_a_question_with_no_cadence_never_surfaces(self, cli_runner, test_session):
        make_question(test_session, "Model emergent question", None, first_asked_days_ago=400)

        result = run(cli_runner, test_session, forecast_command, ["--due"])

        assert "Model emergent question" not in result.output
        assert "1 open question(s) carry no cadence" in result.output

    def test_a_prediction_past_its_due_date_awaits_a_verdict(self, cli_runner, test_session):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")
        # Staked legitimately, then time passed: due_by is set directly rather
        # than through `predict`, which refuses a past date at entry.
        p = Prediction(
            question_id=q.id,
            observable_text="Yes -- slips",
            trigger_condition="Operator judgement.",
            author=PREDICTION_AUTHOR_OPERATOR,
            due_by=utcnow() - timedelta(days=3),
            confidence=0.7,
            status=PREDICTION_STATUS_OPEN,
        )
        test_session.add(p)
        test_session.commit()

        result = run(cli_runner, test_session, forecast_command, ["--due"])

        assert "AWAITING YOUR VERDICT (1)" in result.output
        assert "Yes -- slips" in result.output
        assert f"resolve {p.id} --outcome yes|no" in result.output

    def test_a_prediction_not_yet_due_does_not_await_a_verdict(self, cli_runner, test_session):
        q = make_question(test_session, "Does CMMC Phase 2 slip?", "90d")
        run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", future_date(30), "--confidence", "0.7"],
        )

        result = run(cli_runner, test_session, forecast_command, ["--due"])

        assert "AWAITING YOUR VERDICT (0)" in result.output


class TestAuthorSplitInTrackRecord:
    @pytest.fixture
    def mixed_ledger(self, test_session):
        q = Question(
            text="Will the rule slip?",
            normalized_text="will the rule slip",
            status=QUESTION_STATUS_OPEN,
            cadence="30d",
        )
        test_session.add(q)
        test_session.flush()
        run_row = AnalysisRun(run_type="situation_synthesis", status="completed")
        test_session.add(run_row)
        test_session.flush()
        synth = NarrativeSynthesis(analysis_run_id=run_row.id)
        test_session.add(synth)
        test_session.flush()

        # The model's: a triggered and a contradicted observable. If these were
        # counted, the operator's hit rate below would read 66%, not 50%.
        for status in (PREDICTION_STATUS_TRIGGERED, PREDICTION_STATUS_CONTRADICTED):
            test_session.add(
                Prediction(
                    question_id=q.id,
                    observable_text=f"model observable {status}",
                    trigger_condition="coverage",
                    made_in_synthesis_id=synth.id,
                    author=PREDICTION_AUTHOR_MODEL,
                    status=status,
                    resolved_at=utcnow(),
                )
            )
        # The operator's: one right, one wrong -> a 50% hit rate.
        test_session.add(
            Prediction(
                question_id=q.id,
                observable_text="operator claim that held",
                trigger_condition="Operator judgement.",
                author=PREDICTION_AUTHOR_OPERATOR,
                due_by=utcnow() - timedelta(days=1),
                confidence=0.8,
                status=PREDICTION_STATUS_TRIGGERED,
                outcome="yes",
                resolved_at=utcnow(),
                resolution_note="Happened.",
            )
        )
        test_session.add(
            Prediction(
                question_id=q.id,
                observable_text="operator claim that failed",
                trigger_condition="Operator judgement.",
                author=PREDICTION_AUTHOR_OPERATOR,
                due_by=utcnow() - timedelta(days=1),
                confidence=0.6,
                status=PREDICTION_STATUS_CONTRADICTED,
                outcome="no",
                resolved_at=utcnow(),
                resolution_note="Did not happen.",
            )
        )
        test_session.commit()
        return test_session

    def test_hit_rate_counts_operator_predictions_only(self, cli_runner, mixed_ledger):
        result = run(cli_runner, mixed_ledger, predictions_command, ["track-record"])

        assert result.exit_code == 0
        assert "YOUR CALIBRATION (operator predictions only)" in result.output
        assert "Claims staked:        2" in result.output
        assert "Hit rate: 1/2 = 50%" in result.output

    def test_model_predictions_are_reported_under_their_own_heading(self, cli_runner, mixed_ledger):
        result = run(cli_runner, mixed_ledger, predictions_command, ["track-record"])

        assert "MODEL PREDICTIONS (not counted toward your calibration)" in result.output
        assert "2 made | 1 triggered | 1 contradicted" in result.output

    def test_the_two_are_never_mixed(self, cli_runner, mixed_ledger):
        """
        Four predictions exist, two of each author. The calibration block must
        never report four, and the model block must never report a hit rate.
        """
        result = run(cli_runner, mixed_ledger, predictions_command, ["track-record"])

        operator_block, model_block = result.output.split("MODEL PREDICTIONS")
        assert "Claims staked:        4" not in operator_block
        assert "Hit rate" in operator_block
        assert "Hit rate" not in model_block

    def test_a_ledger_with_no_operator_claims_reports_no_figure(self, cli_runner, test_session):
        q = Question(text="Q", normalized_text="q", status=QUESTION_STATUS_OPEN)
        test_session.add(q)
        test_session.flush()
        test_session.add(
            Prediction(
                question_id=q.id,
                observable_text="model observable",
                trigger_condition="coverage",
                author=PREDICTION_AUTHOR_MODEL,
                status=PREDICTION_STATUS_TRIGGERED,
                resolved_at=utcnow(),
            )
        )
        test_session.commit()

        result = run(cli_runner, test_session, predictions_command, ["track-record"])

        assert "You have staked nothing in this window" in result.output
        assert "Hit rate" not in result.output


class TestNoApiKeyAndNoNetwork:
    """
    Every command in the loop is local database work. Acceptance requires that
    they work with no ANTHROPIC_API_KEY and make no network call, so the socket
    is removed outright rather than the key merely unset.
    """

    @pytest.fixture
    def no_network(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        def _blocked(*args, **kwargs):
            raise AssertionError("A calibration-loop command attempted a network call.")

        monkeypatch.setattr(socket, "socket", _blocked)
        monkeypatch.setattr(socket, "create_connection", _blocked)

    def test_the_whole_loop_runs_offline(self, cli_runner, test_session, no_network):
        added = run(
            cli_runner,
            test_session,
            questions_command,
            ["add", "Does the rule slip?", "--cadence", "7d"],
        )
        assert added.exit_code == 0
        q = test_session.query(Question).one()

        staked = run(
            cli_runner,
            test_session,
            predict_command,
            [str(q.id), "Yes -- slips", "--by", future_date(20), "--confidence", "0.7"],
        )
        assert staked.exit_code == 0
        p = test_session.query(Prediction).one()

        due = run(cli_runner, test_session, forecast_command, ["--due"])
        assert due.exit_code == 0

        resolved = run(
            cli_runner,
            test_session,
            resolve_command,
            [str(p.id), "--outcome", "yes", "--note", "It slipped."],
        )
        assert resolved.exit_code == 0

        record = run(cli_runner, test_session, predictions_command, ["track-record"])
        assert record.exit_code == 0
        assert "Hit rate: 1/1 = 100%" in record.output
