"""
The RSS fetcher, seen through the adapter contract.

These tests assert the wrapper adds nothing: an item read through RSSAdapter is
what RSSFetcher.normalize_article would have produced, field for field. What
the wrapper *does* add is the one distinction the raw fetcher does not make --
unreachable is an error, empty is a result.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.rss.fetcher import RSSFetcher
from src.sources.base import SourceUnavailable
from src.sources.rss_adapter import RSSAdapter

FEED_URL = "https://example.com/feed.rss"


def adapter_with(fetcher: RSSFetcher) -> RSSAdapter:
    return RSSAdapter(name="Test Feed", url=FEED_URL, category="news", fetcher=fetcher)


def mock_get(fetcher: RSSFetcher, content: bytes):
    """Patch the fetcher's session so no socket is opened."""
    response = MagicMock()
    response.content = content
    response.raise_for_status = MagicMock()
    return patch.object(fetcher.session, "get", new_callable=AsyncMock, return_value=response)


class TestFetch:
    async def test_returns_every_entry_as_a_raw_item(self, sample_rss_response):
        fetcher = RSSFetcher()
        with mock_get(fetcher, sample_rss_response):
            items = await adapter_with(fetcher).fetch(datetime(2020, 1, 1))
        await fetcher.close()

        assert [item.title for item in items] == ["Test Article 1", "Test Article 2"]
        assert items[0].guid == "article-1"
        assert items[0].url == "https://example.com/article1"

    async def test_items_are_identical_to_what_the_fetcher_would_have_stored(
        self, sample_rss_response
    ):
        """The wrapper must not be a second, drifting normalizer."""
        import feedparser

        fetcher = RSSFetcher()
        with mock_get(fetcher, sample_rss_response):
            items = await adapter_with(fetcher).fetch(datetime(2020, 1, 1))
        await fetcher.close()

        parsed = feedparser.parse(sample_rss_response)
        expected = [fetcher.normalize_article(entry, parsed.feed) for entry in parsed.entries]

        assert [item.as_article_fields() for item in items] == expected

    async def test_html_is_cleaned_by_the_fetchers_own_cleaner(self, sample_rss_response_html):
        fetcher = RSSFetcher()
        with mock_get(fetcher, sample_rss_response_html):
            items = await adapter_with(fetcher).fetch(datetime(2020, 1, 1))
        await fetcher.close()

        assert "<" not in items[0].normalized_content
        assert "Full Content" in items[0].normalized_content

    async def test_entries_older_than_since_are_excluded(self, sample_rss_response):
        fetcher = RSSFetcher()
        with mock_get(fetcher, sample_rss_response):
            items = await adapter_with(fetcher).fetch(datetime(2024, 1, 1, 12, 30))
        await fetcher.close()

        # Article 1 is 12:00, article 2 is 13:00 on 2024-01-01.
        assert [item.title for item in items] == ["Test Article 2"]

    async def test_an_empty_feed_is_an_empty_result_not_an_error(self, empty_rss_response):
        fetcher = RSSFetcher()
        with mock_get(fetcher, empty_rss_response):
            items = await adapter_with(fetcher).fetch(datetime(2020, 1, 1))
        await fetcher.close()

        assert items == []


class TestUnavailable:
    async def test_http_failure_raises_rather_than_returning_empty(self):
        """The distinction the whole adapter layer turns on."""
        fetcher = RSSFetcher(max_retries=1)
        with (
            patch.object(
                fetcher.session, "get", new_callable=AsyncMock, side_effect=httpx.HTTPError("boom")
            ),
            pytest.raises(SourceUnavailable) as caught,
        ):
            await adapter_with(fetcher).fetch(datetime(2020, 1, 1))
        await fetcher.close()

        assert caught.value.source == "Test Feed"
        assert "boom" in caught.value.reason


class TestLifecycle:
    async def test_an_injected_fetcher_is_not_closed_by_the_adapter(self, sample_rss_response):
        """The caller owns what the caller made."""
        fetcher = RSSFetcher()
        with (
            mock_get(fetcher, sample_rss_response),
            patch.object(fetcher, "close", new_callable=AsyncMock) as closer,
        ):
            await adapter_with(fetcher).fetch(datetime(2020, 1, 1))

        closer.assert_not_called()
        await fetcher.close()

    async def test_an_owned_fetcher_is_closed(self, sample_rss_response):
        adapter = RSSAdapter(name="Test Feed", url=FEED_URL)
        created = RSSFetcher()

        with (
            mock_get(created, sample_rss_response),
            patch("src.sources.rss_adapter.RSSFetcher", return_value=created),
            patch.object(created, "close", new_callable=AsyncMock) as closer,
        ):
            await adapter.fetch(datetime(2020, 1, 1))

        closer.assert_called_once()
        await created.close()


class TestMetadata:
    def test_carries_the_source_row_fields(self):
        adapter = RSSAdapter(name="Test Feed", url=FEED_URL, category="news")

        assert adapter.name == "Test Feed"
        assert adapter.source_url == FEED_URL
        assert adapter.category == "news"
