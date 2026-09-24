"""
Tests for the `route` CLI command (backlog task 028).

`get_db` is patched with the `_patch_db` pattern from
tests/cli/test_replay_cli.py, so nothing here touches the real database. The
corpus is built from tests/evidence/stubs.py::add_watches / add_observations,
the same builders tests/cli/test_replay_cli.py uses, so the two suites cannot
drift about what the corpus contains.

The stub corpus is published 2026-08-20 to 2026-08-23 and the command's clock
is frozen at 2026-09-01, so `--since 10y` covers the corpus and both stub
watches (expiring 2026-12-15 and 2027-03-31) are live on every day the suite
runs.
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest

from src.cli.route import route_command
from src.database.models import Observation, Route
from tests.evidence.stubs import add_observations, add_watches

SINCE = "10y"


# The stub watches expire 2026-12-15 and 2027-03-31. The command's clock is
# frozen here so the suite does not start failing on 2026-12-16.
FROZEN_NOW = datetime(2026, 9, 1, 8, 0)


@contextmanager
def _patch_db(session):
    """A throwaway session for the command, and a frozen clock beside it."""

    @contextmanager
    def _ctx():
        try:
            yield session
            session.flush()
        except Exception:
            session.rollback()
            raise

    with (
        patch("src.cli.route.get_db", _ctx),
        patch("src.cli.route.utcnow", return_value=FROZEN_NOW),
    ):
        yield


@pytest.fixture
def corpus(test_session):
    """Two watches and four observations; two of the four match a watch."""
    add_watches(test_session)
    add_observations(test_session)
    test_session.flush()
    return test_session


def _hash_for(session, title_fragment: str) -> str:
    for obs in session.query(Observation).all():
        if title_fragment in (obs.payload or {}).get("title", ""):
            return obs.content_hash
    raise AssertionError(f"no observation with '{title_fragment}' in its title")


class TestRouteWrites:
    def test_route_writes_two_route_rows_and_reports_the_count(self, cli_runner, corpus):
        with _patch_db(corpus):
            result = cli_runner.invoke(route_command, ["--since", SINCE])

        assert result.exit_code == 0, result.output
        assert corpus.query(Route).count() == 2
        assert "2 link(s) written" in result.output

    def test_dry_run_writes_nothing_and_says_so(self, cli_runner, corpus):
        with _patch_db(corpus):
            result = cli_runner.invoke(route_command, ["--since", SINCE, "--dry-run"])

        assert result.exit_code == 0, result.output
        assert corpus.query(Route).count() == 0
        assert "Nothing was written" in result.output

    def test_running_route_twice_leaves_two_rows(self, cli_runner, corpus):
        with _patch_db(corpus):
            cli_runner.invoke(route_command, ["--since", SINCE])
            cli_runner.invoke(route_command, ["--since", SINCE])

        assert corpus.query(Route).count() == 2


class TestRebuild:
    def test_rebuild_after_a_stale_route_row_leaves_exactly_the_two_correct_rows(
        self, cli_runner, corpus
    ):
        stale_hash = _hash_for(corpus, "Persimmons")
        corpus.add(
            Route(observation_hash=stale_hash, watch_id="conmon-scope-expands", clause_index=0)
        )
        corpus.flush()

        with _patch_db(corpus):
            result = cli_runner.invoke(route_command, ["--since", SINCE, "--rebuild"])

        assert result.exit_code == 0, result.output
        rows = {(r.observation_hash, r.watch_id) for r in corpus.query(Route).all()}
        assert len(rows) == 2
        assert stale_hash not in {h for h, _ in rows}
        assert (_hash_for(corpus, "continuous monitoring"), "conmon-scope-expands") in rows
        assert (_hash_for(corpus, "Hiring notice"), "hiring-market-tightens") in rows


class TestReport:
    def test_the_report_lists_each_watch_with_new_and_in_window_counts(self, cli_runner, corpus):
        with _patch_db(corpus):
            result = cli_runner.invoke(route_command, ["--since", SINCE])

        assert result.exit_code == 0, result.output
        assert "conmon-scope-expands: 1 new, 1 in window" in result.output
        assert "hiring-market-tightens: 1 new, 1 in window" in result.output

    def test_the_report_lists_unrouted_clusters_with_their_source_name(self, cli_runner, corpus):
        with _patch_db(corpus):
            result = cli_runner.invoke(route_command, ["--since", SINCE])

        assert result.exit_code == 0, result.output
        assert "unrouted, largest clusters first:" in result.output
        assert "Example Agency" in result.output


class TestRefusals:
    def test_an_invalid_since_exits_non_zero(self, cli_runner, corpus):
        with _patch_db(corpus):
            result = cli_runner.invoke(route_command, ["--since", "soon"])

        assert result.exit_code != 0
