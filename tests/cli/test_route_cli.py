"""
Tests for the ``route`` CLI command (backlog task 015).

The acceptance criterion is specific about what ``--dry-run`` has to report:
per watch, how many of the last N observations would route, **and** the unrouted
count **and its clusters**. The last part is the one that is easy to drop, and
it is the whole coverage-gap signal -- so it is asserted on the rendered output
rather than on the report object the command happens to build.
"""

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from src.cli.route import route_command
from src.database.models import RouteCandidate, RSSFeed
from src.database.models import Watch as WatchRow
from src.sources.base import RawItem
from src.sources.observation import store_observation

WIRE = "The county board voted on Tuesday to approve the stormwater levy after a hearing."


def _patch_db(session):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    return patch("src.cli.route.get_db", _ctx)


@pytest.fixture
def corpus(test_session):
    """Two feeds, four observations, one live watch and one expired one."""
    scoop = RSSFeed(url="https://fedscoop.test/rss", name="FedScoop")
    cardinal = RSSFeed(url="https://cardinal.test/rss", name="Cardinal News")
    test_session.add_all([scoop, cardinal])
    test_session.flush()

    items = [
        (scoop, "CISA issues an advisory", "CISA published an advisory today."),
        (scoop, "County approves stormwater levy", WIRE),
        (cardinal, "County approves stormwater levy", WIRE + " Reporting by staff."),
        (cardinal, "Ferry service resumes", "The harbour authority restored the timetable."),
    ]
    for index, (feed, title, body) in enumerate(items):
        store_observation(
            test_session,
            feed,
            RawItem(
                guid=f"g{index}",
                url=f"https://example.test/{index}",
                title=title,
                normalized_content=body,
                published_date=datetime(2026, 8, 20),
            ),
        )

    test_session.add_all(
        [
            WatchRow(
                id="cisa-advisories",
                claim="CISA keeps issuing advisories.",
                belief=0.6,
                decision_key="fedramp-authorization-renewal",
                so_what="It sets the remediation workload.",
                triggers=[{"entities": ["CISA"], "terms": ["advisory"]}],
                expires=date(2027, 3, 31),
                staleness_alert_days=30,
            ),
            WatchRow(
                id="expired-question",
                claim="Something that stopped mattering.",
                belief=0.5,
                decision_key="fedramp-authorization-renewal",
                so_what="It no longer bears on anything.",
                triggers=[{"terms": ["ferry"]}],
                expires=date(2026, 1, 1),
                staleness_alert_days=30,
            ),
        ]
    )
    test_session.flush()
    return test_session


def _run(session, args, tmp_path):
    with _patch_db(session):
        return CliRunner().invoke(route_command, [*args, "--gaps-out", str(tmp_path / "gaps.json")])


class TestDryRunReporting:
    def test_it_reports_per_watch_how_many_would_route(self, corpus, tmp_path):
        result = _run(corpus, ["--dry-run"], tmp_path)

        assert result.exit_code == 0, result.output
        assert "cisa-advisories" in result.output
        assert "4 of 4 stored observation(s)" in result.output

    def test_it_reports_the_unrouted_count(self, corpus, tmp_path):
        result = _run(corpus, ["--dry-run"], tmp_path)

        assert "unrouted" in result.output
        assert "routed" in result.output
        assert "3" in result.output

    def test_it_reports_the_unrouted_clusters_not_just_the_count(self, corpus, tmp_path):
        """
        The landmine. A bare integer makes the coverage-gap signal useless.

        The two copies of the county wire story are near-duplicates and must be
        shown as one cluster of two, with a subject attached.
        """
        result = _run(corpus, ["--dry-run"], tmp_path)

        assert "UNROUTED CLUSTERS" in result.output
        assert "County approves stormwater levy" in result.output
        assert "stormwater" in result.output
        assert "gap terms:" in result.output

    def test_it_names_the_clause_that_fired(self, corpus, tmp_path):
        result = _run(corpus, ["--dry-run"], tmp_path)
        assert "clause 0:" in result.output

    def test_it_names_the_watches_it_skipped_as_expired(self, corpus, tmp_path):
        result = _run(corpus, ["--dry-run"], tmp_path)
        assert "expired-question" in result.output
        assert "skipped 1 expired" in result.output

    def test_it_writes_the_gap_report_where_task_021_can_read_it(self, corpus, tmp_path):
        import json

        result = _run(corpus, ["--dry-run"], tmp_path)
        target = tmp_path / "gaps.json"

        assert target.exists()
        assert str(target) in result.output
        payload = json.loads(target.read_text())
        assert payload["unrouted_observations"] == 3
        assert [c["size"] for c in payload["clusters"]] == [2, 1]

    def test_dry_run_writes_no_route_candidates(self, corpus, tmp_path):
        _run(corpus, ["--dry-run"], tmp_path)
        assert corpus.query(RouteCandidate).count() == 0

    def test_limit_bounds_what_is_considered(self, corpus, tmp_path):
        result = _run(corpus, ["--dry-run", "--limit", "2"], tmp_path)
        assert "2 of 4 stored observation(s)" in result.output


class TestWriting:
    def test_without_dry_run_it_records_the_links(self, corpus, tmp_path):
        result = _run(corpus, [], tmp_path)

        assert result.exit_code == 0, result.output
        assert "1 link(s) inserted, 0 already present" in result.output
        assert corpus.query(RouteCandidate).count() == 1

    def test_running_it_twice_records_them_once(self, corpus, tmp_path):
        _run(corpus, [], tmp_path)
        result = _run(corpus, [], tmp_path)

        assert "0 link(s) inserted, 1 already present" in result.output
        assert corpus.query(RouteCandidate).count() == 1


class TestRefusals:
    def test_it_says_so_when_there_are_no_observations(self, test_session, tmp_path):
        result = _run(test_session, ["--dry-run"], tmp_path)
        assert result.exit_code == 0
        assert "No observations are stored" in result.output
        assert "never 'articles'" in result.output

    def test_it_says_so_when_there_are_no_watches(self, test_session, tmp_path):
        feed = RSSFeed(url="https://fedscoop.test/rss", name="FedScoop")
        test_session.add(feed)
        test_session.flush()
        store_observation(
            test_session,
            feed,
            RawItem(guid="g", url="u", title="anything", normalized_content="text"),
        )

        result = _run(test_session, ["--dry-run"], tmp_path)
        assert "No watches are stored" in result.output

    def test_an_uncompilable_trigger_stops_the_command(self, corpus, tmp_path):
        corpus.query(WatchRow).filter_by(id="cisa-advisories").one().triggers = [{}]
        corpus.flush()

        result = _run(corpus, ["--dry-run"], tmp_path)
        assert result.exit_code != 0
        assert "constrains nothing" in str(result.output) + str(result.exception)


class TestNoModelFlagExists:
    """
    Tier 1 takes no model, no prompt version and no adjudicator.

    Checked against the command's registered parameters rather than against
    anyone's intention, on the same pattern as ``watch``'s invariant-6 test.
    """

    def test_the_command_has_no_model_shaped_option(self):
        names = {param.name for param in route_command.params}
        assert names == {"dry_run", "limit", "gaps_out", "no_gaps"}


def test_route_is_registered_on_the_cli():
    from src.cli.app import COMMAND_DISPATCH, cli

    assert COMMAND_DISPATCH["route"] is route_command
    assert "route" in cli.commands


def test_the_default_gap_path_is_inside_the_data_directory():
    from src.routing.gaps import default_gap_report_path

    path = default_gap_report_path()
    assert path.parts[-2:] == ("routing", "unrouted_clusters.json")
    assert Path(path).is_absolute()
