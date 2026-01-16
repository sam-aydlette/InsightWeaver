"""
Tests for Article Normalizer
"""

from datetime import datetime
from unittest.mock import MagicMock

from src.processors.normalizer import ArticleNormalizer, ArticleStorage


class TestArticleNormalizerInit:
    """Tests for ArticleNormalizer initialization"""

    def test_init_creates_pattern(self):
        """Should compile whitespace pattern on init"""
        normalizer = ArticleNormalizer()

        assert normalizer.whitespace_pattern is not None


class TestNormalizeContent:
    """Tests for content normalization"""

    def test_normalize_empty_content(self):
        """Should return empty string for empty input"""
        normalizer = ArticleNormalizer()

        result = normalizer.normalize_content("")

        assert result == ""

    def test_normalize_none_content(self):
        """Should return empty string for None input"""
        normalizer = ArticleNormalizer()

        result = normalizer.normalize_content(None)

        assert result == ""

    def test_normalize_plain_text(self):
        """Should handle plain text input"""
        normalizer = ArticleNormalizer()

        result = normalizer.normalize_content("Plain text content")

        assert result == "Plain text content"

    def test_normalize_removes_script_tags(self):
        """Should remove script elements"""
        normalizer = ArticleNormalizer()
        html = "<p>Content</p><script>alert('test');</script>"

        result = normalizer.normalize_content(html)

        assert "alert" not in result
        assert "Content" in result

    def test_normalize_removes_style_tags(self):
        """Should remove style elements"""
        normalizer = ArticleNormalizer()
        html = "<style>body { color: red; }</style><p>Content</p>"

        result = normalizer.normalize_content(html)

        assert "color" not in result
        assert "Content" in result

    def test_normalize_removes_nav_tags(self):
        """Should remove nav elements"""
        normalizer = ArticleNormalizer()
        html = "<nav>Menu</nav><p>Main content</p>"

        result = normalizer.normalize_content(html)

        assert "Menu" not in result
        assert "Main content" in result

    def test_normalize_removes_footer_tags(self):
        """Should remove footer elements"""
        normalizer = ArticleNormalizer()
        html = "<p>Content</p><footer>Copyright 2024</footer>"

        result = normalizer.normalize_content(html)

        assert "Copyright" not in result
        assert "Content" in result

    def test_normalize_removes_header_tags(self):
        """Should remove header elements"""
        normalizer = ArticleNormalizer()
        html = "<header>Site Header</header><p>Article content</p>"

        result = normalizer.normalize_content(html)

        assert "Site Header" not in result
        assert "Article content" in result

    def test_normalize_removes_aside_tags(self):
        """Should remove aside elements"""
        normalizer = ArticleNormalizer()
        html = "<p>Main content</p><aside>Sidebar</aside>"

        result = normalizer.normalize_content(html)

        assert "Sidebar" not in result
        assert "Main content" in result

    def test_normalize_cleans_whitespace(self):
        """Should normalize excessive whitespace"""
        normalizer = ArticleNormalizer()
        html = "<p>Content   with    extra     spaces</p>"

        result = normalizer.normalize_content(html)

        assert "  " not in result  # No double spaces
        assert "Content with extra spaces" in result

    def test_normalize_complex_html(self, sample_html_content):
        """Should properly extract main content from complex HTML"""
        normalizer = ArticleNormalizer()

        result = normalizer.normalize_content(sample_html_content)

        assert "Article Title" in result
        assert "main article content" in result
        assert "Site Header" not in result
        assert "Navigation Menu" not in result
        assert "Sidebar Content" not in result
        assert "Site Footer" not in result


class TestIsComplete:
    """Tests for article completeness check"""

    def test_is_complete_with_all_fields(self, sample_article_factory):
        """Should return True for complete article"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(
            title="Test Title",
            normalized_content="Test content",
            published_date=datetime.utcnow(),
        )

        result = normalizer.is_complete(article)

        assert result is True

    def test_is_complete_missing_title(self, sample_article_factory):
        """Should return False for article without title"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(title="", normalized_content="Content")

        result = normalizer.is_complete(article)

        assert result is False

    def test_is_complete_missing_content(self, sample_article_factory):
        """Should return False for article without normalized content"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(title="Title", normalized_content="")

        result = normalizer.is_complete(article)

        assert result is False

    def test_is_complete_missing_date(self, sample_article_factory):
        """Should return False for article without published date"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(
            title="Title", normalized_content="Content", published_date=None
        )

        result = normalizer.is_complete(article)

        assert result is False

    def test_is_complete_whitespace_title(self, sample_article_factory):
        """Should return False for whitespace-only title"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(title="   ", normalized_content="Content")

        result = normalizer.is_complete(article)

        assert result is False


class TestProcessArticle:
    """Tests for article processing"""

    def test_process_article_normalizes_content(self, sample_article_factory):
        """Should normalize content if not already done"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(
            content="<p>HTML content</p>", normalized_content=None
        )

        result = normalizer.process_article(article)

        assert result.normalized_content == "HTML content"

    def test_process_article_sets_word_count(self, sample_article_factory):
        """Should calculate word count"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(
            content="<p>One two three four five</p>", normalized_content=None
        )

        result = normalizer.process_article(article)

        assert result.word_count == 5

    def test_process_article_sets_default_language(self, sample_article_factory):
        """Should set default language to English"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(content="<p>Test</p>", normalized_content=None)
        article.language = None

        result = normalizer.process_article(article)

        assert result.language == "en"

    def test_process_article_skips_if_already_normalized(self, sample_article_factory):
        """Should not re-normalize if content already exists"""
        normalizer = ArticleNormalizer()
        article = sample_article_factory(
            content="<p>New content</p>", normalized_content="Existing normalized"
        )

        result = normalizer.process_article(article)

        assert result.normalized_content == "Existing normalized"


class TestArticleStorageInit:
    """Tests for ArticleStorage initialization"""

    def test_init_with_session(self):
        """Should initialize with database session"""
        mock_db = MagicMock()

        storage = ArticleStorage(mock_db)

        assert storage.db == mock_db
        assert storage.normalizer is not None


class TestStoreArticles:
    """Tests for storing articles"""

    def test_store_articles_returns_count(self, sample_article_factory):
        """Should return count of stored articles"""
        mock_db = MagicMock()
        storage = ArticleStorage(mock_db)
        articles = [sample_article_factory(id=i) for i in range(3)]

        result = storage.store_articles(articles)

        assert result == 3
        assert mock_db.commit.called

    def test_store_articles_empty_list(self):
        """Should handle empty article list"""
        mock_db = MagicMock()
        storage = ArticleStorage(mock_db)

        result = storage.store_articles([])

        assert result == 0

    def test_store_articles_rollback_on_commit_error(self, sample_article_factory):
        """Should rollback on commit error"""
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("Database error")
        storage = ArticleStorage(mock_db)
        articles = [sample_article_factory()]

        result = storage.store_articles(articles)

        assert result == 0
        assert mock_db.rollback.called


class TestGetRecentArticles:
    """Tests for getting recent articles"""

    def test_get_recent_articles_default_hours(self):
        """Should query articles from last 48 hours by default"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        storage = ArticleStorage(mock_db)

        storage.get_recent_articles()

        assert mock_db.query.called

    def test_get_recent_articles_custom_hours(self):
        """Should accept custom hours parameter"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        storage = ArticleStorage(mock_db)

        storage.get_recent_articles(hours=24)

        assert mock_db.query.called


class TestGetArticlesByFeed:
    """Tests for getting articles by feed"""

    def test_get_articles_by_feed_with_limit(self):
        """Should limit results"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        storage = ArticleStorage(mock_db)

        storage.get_articles_by_feed(feed_id=1, limit=50)

        mock_query.limit.assert_called_with(50)


class TestGetCompleteArticles:
    """Tests for getting complete articles"""

    def test_get_complete_articles_filters_incomplete(self, sample_article_factory):
        """Should filter out incomplete articles"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query

        complete = sample_article_factory(
            title="Complete", normalized_content="Content", published_date=datetime.utcnow()
        )
        incomplete = sample_article_factory(title="", normalized_content="", published_date=None)
        mock_query.all.return_value = [complete, incomplete]

        storage = ArticleStorage(mock_db)

        result = storage.get_complete_articles(limit=100)

        assert len(result) == 1
        assert result[0].title == "Complete"
