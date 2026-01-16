"""
Tests for RSS Fetcher
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rss.fetcher import RSSFetcher, create_test_feed


class TestRSSFetcherInit:
    """Tests for RSSFetcher initialization"""

    def test_init_default_values(self):
        """Should initialize with default values"""
        fetcher = RSSFetcher()

        assert fetcher.timeout == 30
        assert fetcher.max_retries == 3

    def test_init_custom_values(self):
        """Should accept custom values"""
        fetcher = RSSFetcher(timeout=60, max_retries=5)

        assert fetcher.timeout == 60
        assert fetcher.max_retries == 5


class TestFetchFeed:
    """Tests for feed fetching"""

    @pytest.mark.asyncio
    async def test_fetch_feed_success(self, sample_rss_response):
        """Should successfully fetch and parse RSS feed"""
        fetcher = RSSFetcher()

        with patch.object(fetcher.session, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.content = sample_rss_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            success, feed_data, error = await fetcher.fetch_feed(
                "https://example.com/feed.rss"
            )

            assert success is True
            assert feed_data is not None
            assert error is None

        await fetcher.close()

    @pytest.mark.asyncio
    async def test_fetch_feed_http_error(self):
        """Should handle HTTP errors with retry"""
        import httpx

        fetcher = RSSFetcher(max_retries=2)

        with patch.object(fetcher.session, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")

            success, feed_data, error = await fetcher.fetch_feed(
                "https://example.com/feed.rss"
            )

            assert success is False
            assert feed_data is None
            assert "HTTP error" in error

        await fetcher.close()

    @pytest.mark.asyncio
    async def test_fetch_feed_unexpected_error(self):
        """Should handle unexpected errors"""
        fetcher = RSSFetcher()

        with patch.object(fetcher.session, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Unexpected error")

            success, feed_data, error = await fetcher.fetch_feed(
                "https://example.com/feed.rss"
            )

            assert success is False
            assert "Unexpected error" in error

        await fetcher.close()


class TestNormalizeArticle:
    """Tests for article normalization"""

    def test_normalize_article_full_entry(self, sample_feedparser_entry):
        """Should normalize full feedparser entry"""
        fetcher = RSSFetcher()

        result = fetcher.normalize_article(sample_feedparser_entry, {})

        assert result["title"] == "Test Article"
        assert result["url"] == "https://example.com/article"
        assert result["guid"] == "article-guid-123"
        assert result["author"] == "Test Author"
        assert result["categories"] == ["news", "tech"]
        assert result["published_date"] is not None

    def test_normalize_article_minimal_entry(self, sample_feedparser_entry_minimal):
        """Should handle minimal feedparser entry"""
        fetcher = RSSFetcher()

        result = fetcher.normalize_article(sample_feedparser_entry_minimal, {})

        assert result["title"] == "Minimal Article"
        assert result["url"] == "https://example.com/minimal"
        assert result["guid"] == "https://example.com/minimal"  # Falls back to link
        assert result["author"] == ""
        assert result["categories"] == []

    def test_normalize_article_extracts_content(self, sample_feedparser_entry):
        """Should extract content from entry"""
        fetcher = RSSFetcher()

        result = fetcher.normalize_article(sample_feedparser_entry, {})

        assert "Full content" in result["content"]

    def test_normalize_article_calculates_word_count(self, sample_feedparser_entry):
        """Should calculate word count"""
        fetcher = RSSFetcher()

        result = fetcher.normalize_article(sample_feedparser_entry, {})

        assert result["word_count"] > 0

    def test_normalize_article_sets_default_language(self, sample_feedparser_entry):
        """Should set default language to English"""
        fetcher = RSSFetcher()

        result = fetcher.normalize_article(sample_feedparser_entry, {})

        assert result["language"] == "en"


class TestCleanHtml:
    """Tests for HTML cleaning"""

    def test_clean_html_basic(self):
        """Should clean basic HTML"""
        fetcher = RSSFetcher()

        result = fetcher.clean_html("<p>Hello World</p>")

        assert result == "Hello World"

    def test_clean_html_removes_script(self):
        """Should remove script tags"""
        fetcher = RSSFetcher()

        result = fetcher.clean_html("<p>Text</p><script>alert('test');</script>")

        assert "alert" not in result
        assert "Text" in result

    def test_clean_html_removes_style(self):
        """Should remove style tags"""
        fetcher = RSSFetcher()

        result = fetcher.clean_html("<style>body{color:red;}</style><p>Text</p>")

        assert "color" not in result
        assert "Text" in result

    def test_clean_html_empty_input(self):
        """Should return empty string for empty input"""
        fetcher = RSSFetcher()

        result = fetcher.clean_html("")

        assert result == ""

    def test_clean_html_none_input(self):
        """Should return empty string for None"""
        fetcher = RSSFetcher()

        result = fetcher.clean_html(None)

        assert result == ""

    def test_clean_html_preserves_text(self):
        """Should preserve text content"""
        fetcher = RSSFetcher()
        html = "<div><h1>Title</h1><p>Paragraph one.</p><p>Paragraph two.</p></div>"

        result = fetcher.clean_html(html)

        assert "Title" in result
        assert "Paragraph one" in result
        assert "Paragraph two" in result


class TestFetchAndStoreFeed:
    """Tests for fetching and storing feeds"""

    @pytest.mark.asyncio
    @patch("src.rss.fetcher.get_db")
    async def test_fetch_and_store_feed_not_found(self, mock_get_db):
        """Should return error for non-existent feed"""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        fetcher = RSSFetcher()

        success, count, error = await fetcher.fetch_and_store_feed(999)

        assert success is False
        assert count == 0
        assert "not found" in error

        await fetcher.close()

    @pytest.mark.asyncio
    @patch("src.rss.fetcher.get_db")
    async def test_fetch_and_store_inactive_feed(self, mock_get_db, mock_inactive_feed):
        """Should return error for inactive feed"""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_inactive_feed
        )

        fetcher = RSSFetcher()

        success, count, error = await fetcher.fetch_and_store_feed(2)

        assert success is False
        assert "inactive" in error

        await fetcher.close()


class TestFetchWithRetry:
    """Tests for retry logic"""

    @pytest.mark.asyncio
    async def test_fetch_with_retry_success(self, sample_rss_response):
        """Should succeed on first attempt"""
        fetcher = RSSFetcher()

        with patch.object(fetcher.session, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.content = sample_rss_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            success, feed_data, error = await fetcher._fetch_with_retry(
                "https://example.com/feed.rss", "Test Feed"
            )

            assert success is True
            assert feed_data is not None
            assert error is None

        await fetcher.close()

    @pytest.mark.asyncio
    async def test_fetch_with_retry_empty_feed(self, empty_rss_response):
        """Should fail for empty feed"""
        fetcher = RSSFetcher()

        with patch.object(fetcher.session, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.content = empty_rss_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            success, feed_data, error = await fetcher._fetch_with_retry(
                "https://example.com/empty.rss", "Empty Feed"
            )

            assert success is False
            assert "no entries" in error

        await fetcher.close()


class TestClose:
    """Tests for closing the fetcher"""

    @pytest.mark.asyncio
    async def test_close_closes_session(self):
        """Should close HTTP client session"""
        fetcher = RSSFetcher()

        with patch.object(fetcher.session, "aclose", new_callable=AsyncMock) as mock_close:
            await fetcher.close()

            mock_close.assert_called_once()


class TestCreateTestFeed:
    """Tests for create_test_feed helper"""

    def test_create_test_feed_new(self):
        """Should create new feed if not exists"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        create_test_feed(mock_db)

        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_test_feed_existing(self):
        """Should return existing feed"""
        mock_db = MagicMock()
        existing_feed = MagicMock()
        existing_feed.name = "Existing Feed"
        mock_db.query.return_value.filter.return_value.first.return_value = existing_feed

        result = create_test_feed(mock_db)

        assert result == existing_feed
        assert not mock_db.add.called

    def test_create_test_feed_custom_values(self):
        """Should accept custom name and URL"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        create_test_feed(mock_db, name="Custom Feed", url="https://custom.com/feed.rss")

        call_args = mock_db.add.call_args[0][0]
        assert call_args.name == "Custom Feed"
        assert call_args.url == "https://custom.com/feed.rss"
