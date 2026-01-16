"""
Tests for Article Deduplicator
"""

from unittest.mock import MagicMock, patch

from src.processors.deduplicator import ArticleDeduplicator, run_deduplication


class TestArticleDeduplicatorInit:
    """Tests for ArticleDeduplicator initialization"""

    def test_init_default_values(self):
        """Should initialize with default values"""
        deduplicator = ArticleDeduplicator()

        assert deduplicator.similarity_threshold == 0.85
        assert deduplicator.time_window_hours == 72

    def test_init_custom_values(self):
        """Should accept custom values"""
        deduplicator = ArticleDeduplicator(similarity_threshold=0.9, time_window_hours=48)

        assert deduplicator.similarity_threshold == 0.9
        assert deduplicator.time_window_hours == 48


class TestGenerateContentHash:
    """Tests for content hash generation"""

    def test_generate_content_hash_basic(self):
        """Should generate consistent hash for same content"""
        deduplicator = ArticleDeduplicator()

        hash1 = deduplicator.generate_content_hash("Title", "Content")
        hash2 = deduplicator.generate_content_hash("Title", "Content")

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex digest length

    def test_generate_content_hash_different_content(self):
        """Should generate different hash for different content"""
        deduplicator = ArticleDeduplicator()

        hash1 = deduplicator.generate_content_hash("Title", "Content A")
        hash2 = deduplicator.generate_content_hash("Title", "Content B")

        assert hash1 != hash2

    def test_generate_content_hash_empty_title(self):
        """Should return empty string for empty title"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator.generate_content_hash("", "Content")

        assert result == ""

    def test_generate_content_hash_empty_content(self):
        """Should return empty string for empty content"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator.generate_content_hash("Title", "")

        assert result == ""

    def test_generate_content_hash_none_values(self):
        """Should return empty string for None values"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator.generate_content_hash(None, None)

        assert result == ""

    def test_generate_content_hash_normalized(self):
        """Should normalize text before hashing (case, punctuation)"""
        deduplicator = ArticleDeduplicator()

        hash1 = deduplicator.generate_content_hash("Test Title!", "Content.")
        hash2 = deduplicator.generate_content_hash("test title", "content")

        assert hash1 == hash2


class TestGenerateTitleHash:
    """Tests for title hash generation"""

    def test_generate_title_hash_basic(self):
        """Should generate consistent hash for same title"""
        deduplicator = ArticleDeduplicator()

        hash1 = deduplicator.generate_title_hash("Breaking News")
        hash2 = deduplicator.generate_title_hash("Breaking News")

        assert hash1 == hash2

    def test_generate_title_hash_empty(self):
        """Should return empty string for empty title"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator.generate_title_hash("")

        assert result == ""

    def test_generate_title_hash_none(self):
        """Should return empty string for None"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator.generate_title_hash(None)

        assert result == ""

    def test_generate_title_hash_normalized(self):
        """Should normalize title before hashing"""
        deduplicator = ArticleDeduplicator()

        hash1 = deduplicator.generate_title_hash("Breaking News!")
        hash2 = deduplicator.generate_title_hash("breaking news")

        assert hash1 == hash2


class TestNormalizeText:
    """Tests for text normalization"""

    def test_normalize_text_lowercase(self):
        """Should convert to lowercase"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator._normalize_text("UPPERCASE TEXT")

        assert result == "uppercase text"

    def test_normalize_text_removes_punctuation(self):
        """Should remove punctuation"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator._normalize_text("Hello, World!")

        assert result == "hello world"

    def test_normalize_text_collapses_whitespace(self):
        """Should collapse multiple whitespace"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator._normalize_text("Multiple   spaces   here")

        assert result == "multiple spaces here"

    def test_normalize_text_strips_edges(self):
        """Should strip leading/trailing whitespace"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator._normalize_text("  Text with spaces  ")

        assert result == "text with spaces"

    def test_normalize_text_empty(self):
        """Should return empty string for empty input"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator._normalize_text("")

        assert result == ""

    def test_normalize_text_none(self):
        """Should return empty string for None"""
        deduplicator = ArticleDeduplicator()

        result = deduplicator._normalize_text(None)

        assert result == ""


class TestFindExactDuplicates:
    """Tests for exact duplicate detection"""

    def test_find_exact_duplicates_no_title(self, sample_article_factory):
        """Should return empty list for article without title"""
        deduplicator = ArticleDeduplicator()
        article = sample_article_factory(title="", normalized_content="Content")
        mock_db = MagicMock()

        result = deduplicator.find_exact_duplicates(article, mock_db)

        assert result == []

    def test_find_exact_duplicates_no_content(self, sample_article_factory):
        """Should return empty list for article without content"""
        deduplicator = ArticleDeduplicator()
        article = sample_article_factory(title="Title", normalized_content="")
        mock_db = MagicMock()

        result = deduplicator.find_exact_duplicates(article, mock_db)

        assert result == []


class TestFindNearDuplicates:
    """Tests for near-duplicate detection"""

    def test_find_near_duplicates_no_title(self, sample_article_factory):
        """Should return empty list for article without title"""
        deduplicator = ArticleDeduplicator()
        article = sample_article_factory(title="")
        mock_db = MagicMock()

        result = deduplicator.find_near_duplicates(article, mock_db)

        assert result == []


class TestMarkAsDuplicate:
    """Tests for marking articles as duplicates"""

    def test_mark_as_duplicate_exact(self, duplicate_article_pair):
        """Should mark exact duplicate correctly"""
        deduplicator = ArticleDeduplicator()
        original, duplicate = duplicate_article_pair
        mock_db = MagicMock()

        deduplicator.mark_as_duplicate(original, duplicate, mock_db)

        assert duplicate.priority_metadata["is_duplicate"] is True
        assert duplicate.priority_metadata["duplicate_of"] == original.id
        assert duplicate.priority_metadata["duplicate_type"] == "exact"
        assert duplicate.priority_score == 0.1

    def test_mark_as_duplicate_near(self, near_duplicate_pair):
        """Should mark near duplicate correctly"""
        deduplicator = ArticleDeduplicator()
        original, duplicate = near_duplicate_pair
        mock_db = MagicMock()

        deduplicator.mark_as_duplicate(original, duplicate, mock_db)

        assert duplicate.priority_metadata["is_duplicate"] is True
        assert duplicate.priority_metadata["duplicate_type"] == "near"

    def test_mark_as_duplicate_initializes_metadata(self, sample_article_factory):
        """Should initialize metadata if None"""
        deduplicator = ArticleDeduplicator()
        original = sample_article_factory(id=1)
        duplicate = sample_article_factory(id=2, priority_metadata=None)
        mock_db = MagicMock()

        deduplicator.mark_as_duplicate(original, duplicate, mock_db)

        assert duplicate.priority_metadata is not None


class TestIsExactDuplicate:
    """Tests for exact duplicate check"""

    def test_is_exact_duplicate_true(self, duplicate_article_pair):
        """Should return True for exact duplicates"""
        deduplicator = ArticleDeduplicator()
        original, duplicate = duplicate_article_pair

        result = deduplicator._is_exact_duplicate(original, duplicate)

        assert result is True

    def test_is_exact_duplicate_false(self, sample_article_factory):
        """Should return False for different content"""
        deduplicator = ArticleDeduplicator()
        article1 = sample_article_factory(
            title="Title A", normalized_content="Content A"
        )
        article2 = sample_article_factory(
            title="Title B", normalized_content="Content B"
        )

        result = deduplicator._is_exact_duplicate(article1, article2)

        assert result is False

    def test_is_exact_duplicate_missing_fields(self, sample_article_factory):
        """Should return False if missing required fields"""
        deduplicator = ArticleDeduplicator()
        article1 = sample_article_factory(title="", normalized_content="Content")
        article2 = sample_article_factory(title="Title", normalized_content="Content")

        result = deduplicator._is_exact_duplicate(article1, article2)

        assert result is False


class TestDeduplicateRecentArticles:
    """Tests for deduplicating recent articles"""

    @patch("src.processors.deduplicator.get_db")
    def test_deduplicate_returns_stats(self, mock_get_db):
        """Should return deduplication statistics"""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        deduplicator = ArticleDeduplicator()

        result = deduplicator.deduplicate_recent_articles(hours=24)

        assert "processed_articles" in result
        assert "url_duplicates" in result
        assert "exact_duplicates" in result
        assert "title_duplicates" in result
        assert "total_duplicates" in result


class TestGetDuplicateStatistics:
    """Tests for duplicate statistics"""

    @patch("src.processors.deduplicator.get_db")
    def test_get_duplicate_statistics_returns_dict(self, mock_get_db):
        """Should return statistics dictionary"""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.all.return_value = []

        deduplicator = ArticleDeduplicator()

        result = deduplicator.get_duplicate_statistics()

        assert "total_articles" in result
        assert "duplicate_articles" in result
        assert "original_articles" in result
        assert "unique_articles" in result
        assert "duplication_rate" in result

    @patch("src.processors.deduplicator.get_db")
    def test_get_duplicate_statistics_zero_articles(self, mock_get_db):
        """Should handle zero articles without division error"""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []

        deduplicator = ArticleDeduplicator()

        result = deduplicator.get_duplicate_statistics()

        assert result["duplication_rate"] == 0.0


class TestRunDeduplication:
    """Tests for convenience function"""

    @patch("src.processors.deduplicator.ArticleDeduplicator")
    def test_run_deduplication_creates_deduplicator(self, mock_class):
        """Should create ArticleDeduplicator and call method"""
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        mock_instance.deduplicate_recent_articles.return_value = {}

        run_deduplication(hours=12)

        mock_class.assert_called_once()
        mock_instance.deduplicate_recent_articles.assert_called_with(hours=12)

    @patch("src.processors.deduplicator.ArticleDeduplicator")
    def test_run_deduplication_default_hours(self, mock_class):
        """Should default to 24 hours"""
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        mock_instance.deduplicate_recent_articles.return_value = {}

        run_deduplication()

        mock_instance.deduplicate_recent_articles.assert_called_with(hours=24)
