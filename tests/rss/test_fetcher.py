"""
Tests for RSS Fetcher
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from src.database.models import Article, Observation, RSSFeed
from src.rss.fetcher import (
    LEGACY_PATH_MESSAGE,
    LegacyWritePathClosed,
    RSSFetcher,
    create_test_feed,
)


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

            success, feed_data, error = await fetcher.fetch_feed("https://example.com/feed.rss")

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

            success, feed_data, error = await fetcher.fetch_feed("https://example.com/feed.rss")

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

            success, feed_data, error = await fetcher.fetch_feed("https://example.com/feed.rss")

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


class TestTheLegacyWritePathIsClosed:
    """
    The legacy article write path refuses instead of writing (task 025).

    ``fetch_and_store_feed`` used to insert Article rows with no Observation
    beside them, which is the one way the corpus could grow rows that Tier 1
    routing can never see. It now raises. These tests drive the real entry
    points -- no mock stands in for the function under test -- and check both
    that the call refuses and that the database is untouched by the attempt.
    """

    @pytest.fixture
    def db_pointed_at_test_engine(self, test_engine, monkeypatch):
        """
        Point src.database.connection at a throwaway engine.

        The legacy path opened its own session through ``get_db`` rather than
        taking one, so proving "it wrote nothing" means giving it a database it
        *could* have written to and finding it empty afterwards.
        """
        import src.database.connection as connection

        Session = sessionmaker(bind=test_engine)
        monkeypatch.setattr(connection, "engine", test_engine)
        monkeypatch.setattr(connection, "SessionLocal", Session)
        session = Session()
        yield session
        session.close()

    @pytest.mark.asyncio
    async def test_fetch_and_store_feed_refuses(self, db_pointed_at_test_engine):
        """The call raises rather than returning a (success, count, error) tuple."""
        db = db_pointed_at_test_engine
        feed = RSSFeed(name="Test Feed", url="https://example.com/feed.rss", category="news")
        db.add(feed)
        db.commit()

        fetcher = RSSFetcher()
        try:
            with pytest.raises(LegacyWritePathClosed, match="legacy RSS write path is closed"):
                await fetcher.fetch_and_store_feed(feed.id)
        finally:
            await fetcher.close()

    @pytest.mark.asyncio
    async def test_the_refused_call_writes_no_article_and_no_observation(
        self, db_pointed_at_test_engine
    ):
        """
        Articles and observations both stay at zero -- in step, at zero.

        The failure this guards against is not "it errors", it is "it errors
        after inserting", which would leave exactly the unroutable rows the
        task exists to prevent.
        """
        db = db_pointed_at_test_engine
        feed = RSSFeed(name="Test Feed", url="https://example.com/feed.rss", category="news")
        db.add(feed)
        db.commit()
        assert db.query(Article).count() == 0
        assert db.query(Observation).count() == 0

        fetcher = RSSFetcher()
        try:
            with pytest.raises(LegacyWritePathClosed):
                await fetcher.fetch_and_store_feed(feed.id)
        finally:
            await fetcher.close()

        db.expire_all()
        assert db.query(Article).count() == 0
        assert db.query(Observation).count() == 0

    @pytest.mark.asyncio
    async def test_the_refused_call_does_not_touch_the_feed_row(self, db_pointed_at_test_engine):
        """
        No last_fetched stamp and no error_count bump.

        The old path counted failures toward auto-deactivation at ten. A closed
        path that still incremented that counter would quietly disable every
        feed in the table after ten attempts.
        """
        db = db_pointed_at_test_engine
        feed = RSSFeed(name="Test Feed", url="https://example.com/feed.rss", category="news")
        db.add(feed)
        db.commit()

        fetcher = RSSFetcher()
        try:
            for _ in range(3):
                with pytest.raises(LegacyWritePathClosed):
                    await fetcher.fetch_and_store_feed(feed.id)
        finally:
            await fetcher.close()

        db.expire_all()
        stored = db.query(RSSFeed).one()
        assert stored.last_fetched is None
        assert stored.error_count == 0
        assert stored.is_active is True

    def test_the_error_names_the_supported_replacement(self):
        """A refusal that does not say what to use instead is a dead end."""
        assert "store_items" in LEGACY_PATH_MESSAGE
        assert "RSSAdapter" in LEGACY_PATH_MESSAGE

    @pytest.mark.asyncio
    async def test_reading_a_feed_still_works(self, sample_rss_response):
        """
        Only the write is closed. fetch_feed and normalize_article are what
        src/sources/rss_adapter.py uses, and they are untouched.
        """
        fetcher = RSSFetcher()

        with patch.object(fetcher.session, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.content = sample_rss_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            success, feed_data, error = await fetcher.fetch_feed("https://example.com/feed.rss")

        assert success is True
        assert len(feed_data.entries) == 2
        assert error is None

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
