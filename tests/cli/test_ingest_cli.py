"""
Tests for the `ingest` CLI command (backlog task 028).

Everything here is offline: `build_configured_adapters` is patched to return
FakeAdapters (mirroring tests/sources/test_runner.py::FakeAdapter) and
`get_db` is patched with the `_patch_db` pattern from
tests/cli/test_replay_cli.py, so nothing here touches config/feeds/ or the
real database.
"""

from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from src.cli.ingest import ingest_command
from src.database.models import Observation
from src.sources.base import RawItem, SourceUnavailable
from src.sources.store import ensure_source, store_items
from src.utils import utcnow


def _patch_db(session):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.flush()
        except Exception:
            session.rollback()
            raise

    return patch("src.cli.ingest.get_db", _ctx)


def _patch_adapters(adapters):
    return patch("src.cli.ingest.build_configured_adapters", return_value=adapters)


def _item(guid: str) -> RawItem:
    return RawItem(
        guid=guid,
        url=f"https://example.gov/{guid}",
        title=f"Title {guid}",
        normalized_content=f"Body of {guid}",
    )


class FakeAdapter:
    """An adapter whose behaviour each test dictates outright."""

    category = "federal_policy"

    def __init__(self, name, items=None, error=None):
        self.name = name
        self.source_url = f"https://example.gov/api/{name}"
        self._items = items or []
        self._error = error
        self.since_seen = None

    async def fetch(self, since):
        self.since_seen = since
        if self._error is not None:
            raise self._error
        return self._items


class TestSuccessfulRun:
    def test_prints_fetched_and_inserted_counts_and_exits_zero(self, cli_runner, test_session):
        adapter = FakeAdapter("Source A", items=[_item("a1"), _item("a2")])

        with _patch_db(test_session), _patch_adapters([adapter]):
            result = cli_runner.invoke(ingest_command, [])

        assert result.exit_code == 0, result.output
        assert "Source A" in result.output
        assert "fetched 2" in result.output
        assert "inserted 2" in result.output

    def test_the_observations_table_holds_the_stored_items(self, cli_runner, test_session):
        adapter = FakeAdapter("Source A", items=[_item("a1"), _item("a2")])

        with _patch_db(test_session), _patch_adapters([adapter]):
            cli_runner.invoke(ingest_command, [])

        assert test_session.query(Observation).count() == 2


class TestUnreachableSource:
    def test_an_unreachable_source_is_printed_as_unreachable(self, cli_runner, test_session):
        good = FakeAdapter("Good Source", items=[_item("a1")])
        bad = FakeAdapter("Bad Source", error=SourceUnavailable("Bad Source", "HTTP 503"))

        with _patch_db(test_session), _patch_adapters([bad, good]):
            result = cli_runner.invoke(ingest_command, [])

        assert "UNREACHABLE" in result.output
        assert "Bad Source" in result.output

    def test_the_command_still_exits_zero_when_another_source_succeeded(
        self, cli_runner, test_session
    ):
        good = FakeAdapter("Good Source", items=[_item("a1")])
        bad = FakeAdapter("Bad Source", error=SourceUnavailable("Bad Source", "HTTP 503"))

        with _patch_db(test_session), _patch_adapters([bad, good]):
            result = cli_runner.invoke(ingest_command, [])

        assert result.exit_code == 0, result.output

    def test_every_source_unreachable_exits_non_zero(self, cli_runner, test_session):
        bad = FakeAdapter("Bad Source", error=SourceUnavailable("Bad Source", "HTTP 503"))

        with _patch_db(test_session), _patch_adapters([bad]):
            result = cli_runner.invoke(ingest_command, [])

        assert result.exit_code != 0


class TestWentSilent:
    def test_a_source_that_produced_before_and_returns_nothing_is_flagged(
        self, cli_runner, test_session
    ):
        adapter = FakeAdapter("Quiet Source", items=[])
        source = ensure_source(test_session, adapter.name, adapter.source_url, adapter.category)
        store_items(test_session, source, [_item("earlier")])
        test_session.flush()

        with _patch_db(test_session), _patch_adapters([adapter]):
            result = cli_runner.invoke(ingest_command, [])

        assert result.exit_code == 0, result.output
        assert "WENT SILENT" in result.output
        assert "SOURCE ALERT" in result.output
        assert "Quiet Source" in result.output


class TestAdapterSet:
    def test_the_command_asks_for_every_configured_feed_including_rss(
        self, cli_runner, test_session
    ):
        seen = {}

        def build(*args, **kwargs):
            seen.update(kwargs)
            return [FakeAdapter("Source A", items=[_item("a1")])]

        with _patch_db(test_session), patch("src.cli.ingest.build_configured_adapters", build):
            result = cli_runner.invoke(ingest_command, [])

        assert result.exit_code == 0, result.output
        assert seen == {"include_rss": True}


class TestSourceFilter:
    def test_filters_sources_by_case_insensitive_substring(self, cli_runner, test_session):
        federal = FakeAdapter("Federal Register", items=[_item("a1")])
        regional = FakeAdapter("Regional Gazette", items=[_item("b1")])

        with _patch_db(test_session), _patch_adapters([federal, regional]):
            result = cli_runner.invoke(ingest_command, ["--source", "federal"])

        assert result.exit_code == 0, result.output
        assert "Federal Register" in result.output
        assert "Regional Gazette" not in result.output

    def test_an_unmatched_filter_exits_non_zero_and_says_nothing_matched(
        self, cli_runner, test_session
    ):
        federal = FakeAdapter("Federal Register", items=[_item("a1")])

        with _patch_db(test_session), _patch_adapters([federal]):
            result = cli_runner.invoke(ingest_command, ["--source", "nonexistent"])

        assert result.exit_code != 0
        assert "nothing matched" in result.output


class TestSinceOption:
    def test_an_invalid_since_exits_non_zero(self, cli_runner, test_session):
        adapter = FakeAdapter("Source A", items=[])

        with _patch_db(test_session), _patch_adapters([adapter]):
            result = cli_runner.invoke(ingest_command, ["--since", "soon"])

        assert result.exit_code != 0

    def test_since_2w_passes_a_window_start_roughly_fourteen_days_back(
        self, cli_runner, test_session
    ):
        adapter = FakeAdapter("Source A", items=[])

        before = utcnow()
        with _patch_db(test_session), _patch_adapters([adapter]):
            result = cli_runner.invoke(ingest_command, ["--since", "2w"])
        after = utcnow()

        assert result.exit_code == 0, result.output
        assert adapter.since_seen is not None
        assert before - timedelta(days=14) <= adapter.since_seen <= after - timedelta(days=14)
