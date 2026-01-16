"""
Tests for Parallel RSS Fetcher
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rss.parallel_fetcher import FetchResult, ParallelRSSFetcher, fetch_all_active_feeds


class TestFetchResult:
    """Tests for FetchResult dataclass"""

    def test_fetch_result_creation(self):
        """Should create FetchResult with all fields"""
        result = FetchResult(
            feed_id=1,
            feed_name="Test Feed",
            success=True,
            articles_count=10,
            error_message=None,
            fetch_time=1.5,
        )

        assert result.feed_id == 1
        assert result.feed_name == "Test Feed"
        assert result.success is True
        assert result.articles_count == 10
        assert result.error_message is None
        assert result.fetch_time == 1.5

    def test_fetch_result_with_error(self):
        """Should create FetchResult with error message"""
        result = FetchResult(
            feed_id=2,
            feed_name="Failed Feed",
            success=False,
            articles_count=0,
            error_message="Connection timeout",
            fetch_time=30.0,
        )

        assert result.success is False
        assert result.error_message == "Connection timeout"


class TestParallelRSSFetcherInit:
    """Tests for ParallelRSSFetcher initialization"""

    def test_init_default_values(self):
        """Should initialize with default values"""
        fetcher = ParallelRSSFetcher()

        assert fetcher.max_concurrent_feeds == 10
        assert fetcher.requests_per_second == 2.0
        assert fetcher.timeout == 30

    def test_init_custom_values(self):
        """Should accept custom values"""
        fetcher = ParallelRSSFetcher(
            max_concurrent_feeds=5, requests_per_second=1.0, timeout=60
        )

        assert fetcher.max_concurrent_feeds == 5
        assert fetcher.requests_per_second == 1.0
        assert fetcher.timeout == 60


class TestFetchAllFeeds:
    """Tests for fetching all feeds"""

    @pytest.mark.asyncio
    async def test_fetch_all_feeds_empty_list(self):
        """Should handle empty feed list"""
        fetcher = ParallelRSSFetcher()

        result = await fetcher.fetch_all_feeds([])

        assert result["total_feeds"] == 0
        assert result["successful_feeds"] == 0
        assert result["total_articles"] == 0

    @pytest.mark.asyncio
    @patch("src.rss.parallel_fetcher.RSSFetcher")
    async def test_fetch_all_feeds_with_feeds(self, mock_fetcher_class, mock_rss_feed):
        """Should process feeds and return summary"""
        mock_fetcher = MagicMock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch_and_store_feed = AsyncMock(return_value=(True, 5, None))
        mock_fetcher.close = AsyncMock()

        fetcher = ParallelRSSFetcher()

        result = await fetcher.fetch_all_feeds([mock_rss_feed])

        assert result["total_feeds"] == 1
        assert result["successful_feeds"] == 1
        assert result["total_articles"] == 5
        assert "timestamp" in result

    @pytest.mark.asyncio
    @patch("src.rss.parallel_fetcher.RSSFetcher")
    async def test_fetch_all_feeds_handles_errors(self, mock_fetcher_class, mock_rss_feed):
        """Should handle feed errors gracefully"""
        mock_fetcher = MagicMock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch_and_store_feed = AsyncMock(
            return_value=(False, 0, "Network error")
        )
        mock_fetcher.close = AsyncMock()

        fetcher = ParallelRSSFetcher()

        result = await fetcher.fetch_all_feeds([mock_rss_feed])

        assert result["failed_feeds"] == 1
        assert result["successful_feeds"] == 0
        # error_summary contains error type -> count
        assert "Network error" in result["error_summary"]
        assert result["error_summary"]["Network error"] == 1


class TestRateLimitedFetch:
    """Tests for rate-limited fetching"""

    @pytest.mark.asyncio
    @patch("src.rss.parallel_fetcher.RSSFetcher")
    async def test_rate_limited_fetch_success(self, mock_fetcher_class, mock_rss_feed):
        """Should return FetchResult on success"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_and_store_feed = AsyncMock(return_value=(True, 3, None))

        fetcher = ParallelRSSFetcher()

        result = await fetcher._rate_limited_fetch(mock_fetcher, mock_rss_feed)

        assert isinstance(result, FetchResult)
        assert result.success is True
        assert result.articles_count == 3
        assert result.feed_name == mock_rss_feed.name

    @pytest.mark.asyncio
    @patch("src.rss.parallel_fetcher.RSSFetcher")
    async def test_rate_limited_fetch_exception(self, mock_fetcher_class, mock_rss_feed):
        """Should handle exceptions during fetch"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_and_store_feed = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        fetcher = ParallelRSSFetcher()

        result = await fetcher._rate_limited_fetch(mock_fetcher, mock_rss_feed)

        assert result.success is False
        assert "Unexpected error" in result.error_message


class TestGenerateSummary:
    """Tests for summary generation"""

    def test_generate_summary_basic(self):
        """Should generate correct summary statistics"""
        fetcher = ParallelRSSFetcher()

        results = [
            FetchResult(1, "Feed1", True, 10, None, 1.0),
            FetchResult(2, "Feed2", True, 5, None, 1.5),
            FetchResult(3, "Feed3", False, 0, "Error", 2.0),
        ]

        summary = fetcher._generate_summary(results, total_time=5.0)

        assert summary["total_feeds"] == 3
        assert summary["successful_feeds"] == 2
        assert summary["failed_feeds"] == 1
        assert summary["total_articles"] == 15
        assert summary["total_time"] == 5.0
        assert summary["avg_fetch_time"] == 1.25  # (1.0 + 1.5) / 2

    def test_generate_summary_all_failed(self):
        """Should handle all failed feeds"""
        fetcher = ParallelRSSFetcher()

        results = [
            FetchResult(1, "Feed1", False, 0, "Error 1", 1.0),
            FetchResult(2, "Feed2", False, 0, "Error 2", 1.0),
        ]

        summary = fetcher._generate_summary(results, total_time=2.0)

        assert summary["successful_feeds"] == 0
        assert summary["failed_feeds"] == 2
        assert summary["avg_fetch_time"] == 0.0

    def test_generate_summary_empty_feeds(self):
        """Should track empty feeds separately"""
        fetcher = ParallelRSSFetcher()

        results = [
            FetchResult(1, "Feed1", True, 10, None, 1.0),
            FetchResult(2, "EmptyFeed", True, 0, None, 1.0),
        ]

        summary = fetcher._generate_summary(results, total_time=2.0)

        assert "EmptyFeed" in summary["empty_feeds"]
        assert summary["successful_feeds"] == 2

    def test_generate_summary_error_grouping(self):
        """Should group errors by type"""
        fetcher = ParallelRSSFetcher()

        results = [
            FetchResult(1, "Feed1", False, 0, "HTTP error: 404", 1.0),
            FetchResult(2, "Feed2", False, 0, "HTTP error: 500", 1.0),
            FetchResult(3, "Feed3", False, 0, "Timeout error", 1.0),
        ]

        summary = fetcher._generate_summary(results, total_time=3.0)

        assert "HTTP error" in summary["error_summary"]
        assert summary["error_summary"]["HTTP error"] == 2
        assert summary["error_summary"]["Timeout error"] == 1


class TestEmptyResults:
    """Tests for empty results structure"""

    def test_empty_results_structure(self):
        """Should return correct empty results structure"""
        fetcher = ParallelRSSFetcher()

        result = fetcher._empty_results()

        assert result["total_feeds"] == 0
        assert result["successful_feeds"] == 0
        assert result["failed_feeds"] == 0
        assert result["total_articles"] == 0
        assert result["total_time"] == 0.0
        assert result["avg_fetch_time"] == 0.0
        assert result["articles_per_second"] == 0.0
        assert result["feeds_per_second"] == 0.0
        assert result["error_summary"] == {}
        assert result["empty_feeds"] == []
        assert result["failed_feeds_list"] == []
        assert "timestamp" in result


class TestFetchAllActiveFeeds:
    """Tests for fetch_all_active_feeds convenience function"""

    @pytest.mark.asyncio
    @patch("src.rss.parallel_fetcher.get_db")
    async def test_fetch_all_active_feeds_no_feeds(self, mock_get_db):
        """Should handle no active feeds"""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = await fetch_all_active_feeds()

        assert result["total_feeds"] == 0

    @pytest.mark.asyncio
    @patch("src.rss.parallel_fetcher.ParallelRSSFetcher")
    @patch("src.rss.parallel_fetcher.get_db")
    async def test_fetch_all_active_feeds_with_feeds(
        self, mock_get_db, mock_parallel_class
    ):
        """Should fetch active feeds from database"""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        feed_data = MagicMock()
        feed_data.id = 1
        feed_data.name = "Test Feed"
        feed_data.url = "https://example.com/feed.rss"
        feed_data.category = "news"
        mock_db.query.return_value.filter.return_value.all.return_value = [feed_data]

        mock_fetcher = MagicMock()
        mock_parallel_class.return_value = mock_fetcher
        mock_fetcher.fetch_all_feeds = AsyncMock(return_value={"total_feeds": 1})

        result = await fetch_all_active_feeds(max_concurrent=5, rate_limit=1.0)

        mock_parallel_class.assert_called_with(
            max_concurrent_feeds=5, requests_per_second=1.0
        )
        assert result["total_feeds"] == 1
