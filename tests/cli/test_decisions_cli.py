"""
Tests for the `decisions` CLI command.
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest

from src.cli.decisions import decisions_command
from src.database.models import (
    DECISION_STATUS_DECIDED,
    DECISION_STATUS_OPEN,
    AnalysisRun,
    Decision,
    DecisionEvidence,
    DecisionFactor,
    NarrativeSynthesis,
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

    return patch("src.cli.decisions.get_db", _ctx)


@pytest.fixture
def populated_session(test_session):
    d = Decision(
        name="housing market monitoring", decision_type="housing", status=DECISION_STATUS_OPEN
    )
    test_session.add(d)
    test_session.flush()
    factor = DecisionFactor(
        decision_id=d.id, name="interest rates", what_would_update_me="a Fed move"
    )
    test_session.add(factor)
    test_session.flush()

    run = AnalysisRun(run_type="situation_synthesis", status="completed")
    test_session.add(run)
    test_session.flush()
    synth = NarrativeSynthesis(analysis_run_id=run.id)
    test_session.add(synth)
    test_session.flush()

    test_session.add(
        DecisionEvidence(
            decision_id=d.id,
            factor_id=factor.id,
            synthesis_id=synth.id,
            situation_excerpt="The Fed held rates steady.",
            direction="complicates",
            epistemic_status="single_source",
        )
    )
    test_session.commit()
    return test_session, d, factor


class TestList:
    def test_lists_open_decisions(self, cli_runner, populated_session):
        session, d, _ = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(decisions_command, ["list"])
        assert result.exit_code == 0
        assert f"D{d.id}" in result.output
        assert "housing market monitoring" in result.output
        assert "1 factor(s)" in result.output
        assert "1 evidence record(s)" in result.output

    def test_empty(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(decisions_command, ["list"])
        assert result.exit_code == 0
        assert "No open decisions" in result.output


class TestShow:
    def test_shows_factors_and_evidence(self, cli_runner, populated_session):
        session, d, factor = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(decisions_command, ["show", str(d.id)])
        assert result.exit_code == 0
        assert "housing market monitoring" in result.output
        assert f"F{factor.id}" in result.output
        assert "interest rates" in result.output
        assert "The Fed held rates steady." in result.output
        assert "complicates" in result.output

    def test_unknown(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(decisions_command, ["show", "9999"])
        assert result.exit_code == 0
        assert "not found" in result.output


class TestAdd:
    def test_add_decision(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(
                decisions_command,
                ["add", "--name", "career move", "--type", "career"],
            )
        assert result.exit_code == 0
        assert "Added decision" in result.output
        d = test_session.query(Decision).filter_by(name="career move").first()
        assert d is not None
        assert d.decision_type == "career"

    def test_add_rejects_bad_type(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(
                decisions_command,
                ["add", "--name", "x", "--type", "nonsense"],
            )
        assert result.exit_code != 0


class TestResolve:
    def test_resolve_open_decision(self, cli_runner, populated_session):
        session, d, _ = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(
                decisions_command,
                ["resolve", str(d.id), "--note", "Bought a house."],
            )
        assert result.exit_code == 0
        assert "decided" in result.output
        session.refresh(d)
        assert d.status == DECISION_STATUS_DECIDED
        assert d.notes == "Bought a house."

    def test_cannot_resolve_twice(self, cli_runner, populated_session):
        session, d, _ = populated_session
        d.status = DECISION_STATUS_DECIDED
        d.decided_at = datetime.utcnow()
        session.commit()
        with _patch_db(session):
            result = cli_runner.invoke(decisions_command, ["resolve", str(d.id), "--note", "..."])
        assert result.exit_code == 0
        assert "already" in result.output


class TestFactorAdd:
    def test_add_factor(self, cli_runner, populated_session):
        session, d, _ = populated_session
        with _patch_db(session):
            result = cli_runner.invoke(
                decisions_command,
                [
                    "factor",
                    "add",
                    str(d.id),
                    "--name",
                    "commute time",
                    "--update-when",
                    "a new rail line",
                ],
            )
        assert result.exit_code == 0
        assert "Added factor" in result.output
        factor = session.query(DecisionFactor).filter_by(name="commute time").first()
        assert factor is not None
        assert factor.what_would_update_me == "a new rail line"

    def test_add_factor_to_missing_decision(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(
                decisions_command,
                ["factor", "add", "9999", "--name", "x"],
            )
        assert result.exit_code == 0
        assert "not found" in result.output
