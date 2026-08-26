"""
The silent-zero watchdog and the unreachable-source path.

This is the failure class backlog task 005 names as the one that matters: a
misconfigured filter or a changed API contract yields an empty fetch, a thin
brief, and no error.
"""

from datetime import datetime

import pytest

from src.database.models import Article, RSSFeed
from src.sources.base import RawItem, SourceUnavailable
from src.sources.runner import (
    ADAPTER_FACTORIES,
    AdapterRunSummary,
    IngestResult,
    build_configured_adapters,
    non_rss_adapter_names,
    non_rss_source_urls,
    run_adapter,
    run_adapters,
    run_configured_adapters,
)

SINCE = datetime(2026, 8, 17)


class FakeAdapter:
    """An adapter whose behaviour each test dictates outright."""

    name = "Fake Source"
    source_url = "https://example.gov/api"
    category = "federal_policy"

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = 0

    async def fetch(self, since):
        self.calls += 1
        response = self._responses[min(self.calls - 1, len(self._responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response


def item(guid: str) -> RawItem:
    return RawItem(
        guid=guid,
        url=f"https://example.gov/{guid}",
        title=f"Title {guid}",
        normalized_content=f"Body of {guid}",
        published_date=datetime(2026, 8, 20),
    )


class TestZeroItemsWatchdog:
    async def test_zero_after_some_is_loud(self, db_factory, caplog):
        """The acceptance case: it returned items before, it returns none now."""
        adapter = FakeAdapter([item("a"), item("b")], [])

        first = await run_adapter(adapter, SINCE, db_factory=db_factory)
        assert first.inserted == 2

        with caplog.at_level("ERROR"):
            second = await run_adapter(adapter, SINCE, db_factory=db_factory)

        assert second.fetched == 0
        assert second.went_silent is True
        assert second.error is None  # it answered; it just answered "nothing"
        messages = [record.message for record in caplog.records]
        assert any("SOURCE WENT SILENT" in message for message in messages)
        assert any("Fake Source" in message for message in messages)

    async def test_zero_on_a_source_that_never_produced_is_not_an_alarm(self, db_factory, caplog):
        """A first run against a source with no history has nothing to compare."""
        with caplog.at_level("ERROR"):
            result = await run_adapter(FakeAdapter([]), SINCE, db_factory=db_factory)

        assert result.fetched == 0
        assert result.went_silent is False
        assert not [r for r in caplog.records if "SOURCE WENT SILENT" in r.message]

    async def test_inserting_zero_duplicates_is_not_the_alarm(self, db_factory, caplog):
        """Re-running over unchanged content inserts nothing and that is fine."""
        adapter = FakeAdapter([item("a")])

        await run_adapter(adapter, SINCE, db_factory=db_factory)
        with caplog.at_level("ERROR"):
            second = await run_adapter(adapter, SINCE, db_factory=db_factory)

        assert second.fetched == 1
        assert second.inserted == 0
        assert second.went_silent is False
        assert not [r for r in caplog.records if "SOURCE WENT SILENT" in r.message]

    async def test_recovery_clears_the_flag(self, db_factory):
        adapter = FakeAdapter([item("a")], [], [item("b")])

        await run_adapter(adapter, SINCE, db_factory=db_factory)
        silent = await run_adapter(adapter, SINCE, db_factory=db_factory)
        recovered = await run_adapter(adapter, SINCE, db_factory=db_factory)

        assert silent.went_silent is True
        assert recovered.went_silent is False
        assert recovered.inserted == 1


class TestUnreachable:
    async def test_source_unavailable_is_an_error_not_an_empty_run(self, db_factory, caplog):
        adapter = FakeAdapter(SourceUnavailable("Fake Source", "HTTP 503"))

        with caplog.at_level("ERROR"):
            result = await run_adapter(adapter, SINCE, db_factory=db_factory)

        assert result.success is False
        assert result.error == "HTTP 503"
        assert result.fetched == 0
        assert any("SOURCE UNREACHABLE" in record.message for record in caplog.records)

    async def test_failure_is_recorded_on_the_source_row(self, db_factory):
        await run_adapter(
            FakeAdapter(SourceUnavailable("Fake Source", "HTTP 503")),
            SINCE,
            db_factory=db_factory,
        )

        with db_factory() as db:
            row = db.query(RSSFeed).filter(RSSFeed.url == FakeAdapter.source_url).one()
            assert row.last_error == "HTTP 503"
            assert row.error_count == 1

    async def test_an_unexpected_adapter_bug_is_still_an_outage(self, db_factory):
        result = await run_adapter(
            FakeAdapter(ValueError("adapter bug")), SINCE, db_factory=db_factory
        )

        assert result.success is False
        assert "ValueError" in (result.error or "")

    async def test_a_failed_run_writes_no_articles(self, db_factory):
        await run_adapter(
            FakeAdapter(SourceUnavailable("Fake Source", "boom")), SINCE, db_factory=db_factory
        )

        with db_factory() as db:
            assert db.query(Article).count() == 0


class TestSummary:
    async def test_alerts_name_both_failure_kinds(self, db_factory):
        good = FakeAdapter([item("a")])
        await run_adapter(good, SINCE, db_factory=db_factory)

        summary = AdapterRunSummary(
            results=[
                IngestResult(source="Down", error="HTTP 500"),
                IngestResult(source="Quiet", went_silent=True),
                IngestResult(source="Fine", fetched=3, inserted=3),
            ]
        )

        assert summary.total_sources == 3
        assert summary.successful_sources == 2
        assert summary.total_articles == 3
        assert any("UNREACHABLE" in line for line in summary.alerts)
        assert any("RETURNED ZERO ITEMS" in line for line in summary.alerts)
        assert not any("Fine" in line for line in summary.alerts)

    async def test_a_clean_run_raises_no_alerts(self, db_factory):
        summary = await run_adapters([FakeAdapter([item("a")])], SINCE, db_factory=db_factory)

        assert summary.alerts == []
        assert summary.as_dict()["total_articles"] == 1

    async def test_as_dict_is_serializable_stage_output(self, db_factory):
        summary = await run_adapters([FakeAdapter([item("a")])], SINCE, db_factory=db_factory)
        payload = summary.as_dict()

        assert payload["total_sources"] == 1
        assert payload["failed_sources"] == 0
        assert payload["sources"][0]["source"] == "Fake Source"

    async def test_one_failing_source_does_not_stop_the_others(self, db_factory):
        summary = await run_adapters(
            [FakeAdapter(SourceUnavailable("Fake Source", "boom")), FakeAdapter([item("a")])],
            SINCE,
            db_factory=db_factory,
        )

        assert summary.total_sources == 2
        assert summary.successful_sources == 1
        assert summary.total_articles == 1


class TestConfiguredAdapters:
    def test_the_shipped_config_builds_its_adapters(self):
        adapters = build_configured_adapters()

        assert [adapter.name for adapter in adapters] == ["Federal Register - Documents API"]

    def test_the_shipped_config_declares_the_federal_register_adapter(self):
        assert non_rss_adapter_names() == {"federal_register"}

    def test_non_rss_urls_are_kept_away_from_the_rss_fetcher(self):
        urls = non_rss_source_urls()

        assert "https://www.federalregister.gov/api/v1/documents.json" in urls
        # The Federal Register RSS feed is still RSS and must not be excluded.
        assert "https://www.federalregister.gov/documents/feeds/public-inspection.xml" not in urls

    def test_every_declared_adapter_has_a_factory(self):
        assert non_rss_adapter_names() <= set(ADAPTER_FACTORIES)

    def test_an_unknown_adapter_name_is_an_error_not_a_skipped_source(self, tmp_path):
        (tmp_path / "feeds.json").write_text(
            '{"feeds": [{"name": "X", "url": "https://x.example/api", "adapter": "telepathy",'
            ' "applicability": {}}]}',
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="telepathy"):
            build_configured_adapters(tmp_path)

    async def test_no_configured_adapters_is_an_empty_summary(self, tmp_path, db_factory):
        (tmp_path / "feeds.json").write_text(
            '{"feeds": [{"name": "X", "url": "https://x.example/f.rss", "applicability": {}}]}',
            encoding="utf-8",
        )

        summary = await run_configured_adapters(feeds_dir=tmp_path, db_factory=db_factory)

        assert summary.total_sources == 0
        assert summary.alerts == []
