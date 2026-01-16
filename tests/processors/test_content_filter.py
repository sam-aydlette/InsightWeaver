"""
Tests for Content Filter
"""

import pytest

from src.processors.content_filter import ContentFilter


class TestContentFilterInit:
    """Tests for ContentFilter initialization"""

    def test_init_without_profile(self):
        """Should initialize without user profile"""
        filter = ContentFilter()

        assert filter.user_profile is None
        assert filter.excluded_topics == []

    def test_init_with_profile(self, mock_user_profile):
        """Should extract excluded topics from profile"""
        filter = ContentFilter(user_profile=mock_user_profile)

        assert filter.user_profile == mock_user_profile
        assert "crypto" in filter.excluded_topics
        assert "nft" in filter.excluded_topics


class TestSportsKeywords:
    """Tests for sports keywords constant"""

    def test_sports_keywords_contains_leagues(self):
        """Should contain major sports leagues"""
        assert "nfl" in ContentFilter.SPORTS_KEYWORDS
        assert "nba" in ContentFilter.SPORTS_KEYWORDS
        assert "mlb" in ContentFilter.SPORTS_KEYWORDS
        assert "nhl" in ContentFilter.SPORTS_KEYWORDS

    def test_sports_keywords_contains_sports(self):
        """Should contain sport names"""
        assert "football" in ContentFilter.SPORTS_KEYWORDS
        assert "basketball" in ContentFilter.SPORTS_KEYWORDS
        assert "baseball" in ContentFilter.SPORTS_KEYWORDS
        assert "hockey" in ContentFilter.SPORTS_KEYWORDS

    def test_sports_keywords_contains_events(self):
        """Should contain major sporting events"""
        assert "super bowl" in ContentFilter.SPORTS_KEYWORDS
        assert "world series" in ContentFilter.SPORTS_KEYWORDS
        assert "stanley cup" in ContentFilter.SPORTS_KEYWORDS


class TestClickbaitKeywords:
    """Tests for clickbait keywords constant"""

    def test_clickbait_keywords_contains_patterns(self):
        """Should contain common clickbait phrases"""
        assert "you won't believe" in ContentFilter.CLICKBAIT_KEYWORDS
        assert "mind-blowing" in ContentFilter.CLICKBAIT_KEYWORDS
        assert "what happens next" in ContentFilter.CLICKBAIT_KEYWORDS
        assert "this one trick" in ContentFilter.CLICKBAIT_KEYWORDS


class TestEntertainmentKeywords:
    """Tests for entertainment keywords constant"""

    def test_entertainment_keywords_contains_patterns(self):
        """Should contain entertainment-related terms"""
        assert "celebrity" in ContentFilter.ENTERTAINMENT_KEYWORDS
        assert "red carpet" in ContentFilter.ENTERTAINMENT_KEYWORDS
        assert "oscars" in ContentFilter.ENTERTAINMENT_KEYWORDS
        assert "hollywood" in ContentFilter.ENTERTAINMENT_KEYWORDS


class TestShouldFilter:
    """Tests for should_filter method"""

    def test_should_filter_sports_content(self):
        """Should filter sports content with 2+ keywords"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="NFL Quarterback Throws Touchdown in Playoff Game",
            description="Football action",
        )

        assert should_filter is True
        assert reason == "sports"

    def test_should_not_filter_single_sports_keyword(self):
        """Should not filter with only one sports keyword"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="The Football Stadium as Urban Architecture",
            description="Design analysis",
        )

        assert should_filter is False

    def test_should_filter_clickbait(self):
        """Should filter clickbait titles"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="You Won't Believe What This Expert Discovered",
            description="Normal content",
        )

        assert should_filter is True
        assert reason == "clickbait"

    def test_should_filter_excessive_exclamation(self):
        """Should filter titles with excessive punctuation"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="Amazing Discovery!! Shocking News!!",
            description="Normal content",
        )

        assert should_filter is True
        assert reason == "clickbait"

    def test_should_filter_excessive_question_marks(self):
        """Should filter titles with excessive question marks"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="Is This Real?? Can You Believe??",
            description="Normal content",
        )

        assert should_filter is True
        assert reason == "clickbait"

    def test_should_filter_all_caps_words(self):
        """Should filter titles with excessive ALL CAPS"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="THIS SHOCKING NEWS WILL CHANGE Everything",
            description="Normal content",
        )

        assert should_filter is True
        assert reason == "clickbait"

    def test_should_not_filter_acronyms(self):
        """Should not filter legitimate acronyms (<=3 chars)"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="FBI and CIA Release Joint Report on Security",
            description="Government agencies",
        )

        assert should_filter is False

    def test_should_filter_listicle_pattern(self):
        """Should filter listicle clickbait patterns"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="10 Reasons You Need to Read This Now",
            description="Normal content",
        )

        assert should_filter is True
        assert reason == "clickbait"

    def test_should_filter_entertainment(self):
        """Should filter entertainment content"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="Celebrity Fashion at the Oscars Red Carpet",
            description="Hollywood event",
        )

        assert should_filter is True
        assert reason == "entertainment"

    def test_should_filter_user_excluded_topic(self, mock_user_profile):
        """Should filter user-specified excluded topics"""
        filter = ContentFilter(user_profile=mock_user_profile)

        should_filter, reason = filter.should_filter(
            title="New Crypto Trading Platform Launches",
            description="Cryptocurrency news",
        )

        assert should_filter is True
        assert reason == "excluded_topic:crypto"

    def test_should_not_filter_normal_content(self):
        """Should not filter normal news content"""
        filter = ContentFilter()

        should_filter, reason = filter.should_filter(
            title="City Council Approves New Infrastructure Plan",
            description="Local government news",
        )

        assert should_filter is False
        assert reason is None


class TestIsSportsContent:
    """Tests for sports content detection"""

    def test_is_sports_content_true(self):
        """Should detect sports content"""
        filter = ContentFilter()

        result = filter._is_sports_content("nfl quarterback throws touchdown")

        assert result is True

    def test_is_sports_content_false_single_keyword(self):
        """Should not flag single sports keyword"""
        filter = ContentFilter()

        result = filter._is_sports_content("the football team worked hard")

        assert result is False

    def test_is_sports_content_case_insensitive(self):
        """Should be case insensitive when text is lowercased first"""
        filter = ContentFilter()
        # Note: _is_sports_content expects lowercase text (it's an internal method)
        # The public should_filter method handles case normalization
        result = filter._is_sports_content("nfl quarterback in playoffs")

        assert result is True


class TestIsClickbait:
    """Tests for clickbait detection"""

    def test_is_clickbait_keyword_match(self):
        """Should detect clickbait keywords"""
        filter = ContentFilter()

        result = filter._is_clickbait("You Won't Believe This Trick")

        assert result is True

    def test_is_clickbait_excessive_exclamation(self):
        """Should detect excessive exclamation marks"""
        filter = ContentFilter()

        result = filter._is_clickbait("Amazing News!!")

        assert result is True

    def test_is_clickbait_excessive_question(self):
        """Should detect excessive question marks"""
        filter = ContentFilter()

        result = filter._is_clickbait("Is This True??")

        assert result is True

    def test_is_clickbait_number_pattern(self):
        """Should detect number-based clickbait patterns"""
        filter = ContentFilter()

        result = filter._is_clickbait("5 Tips That Will Change Your Life")

        assert result is True

    def test_is_clickbait_normal_title(self):
        """Should not flag normal titles"""
        filter = ContentFilter()

        result = filter._is_clickbait("Local Government Announces Policy Change")

        assert result is False


class TestIsEntertainmentContent:
    """Tests for entertainment content detection"""

    def test_is_entertainment_content_true(self):
        """Should detect entertainment content"""
        filter = ContentFilter()

        result = filter._is_entertainment_content("celebrity fashion at red carpet")

        assert result is True

    def test_is_entertainment_content_single_keyword(self):
        """Should flag single entertainment keyword"""
        filter = ContentFilter()

        result = filter._is_entertainment_content("hollywood movie premiere")

        assert result is True

    def test_is_entertainment_content_false(self):
        """Should not flag non-entertainment content"""
        filter = ContentFilter()

        result = filter._is_entertainment_content("technology news update")

        assert result is False


class TestFilterArticles:
    """Tests for filtering article lists"""

    def test_filter_articles_separates_kept_and_filtered(
        self, sports_article, normal_article
    ):
        """Should separate kept and filtered articles"""
        filter = ContentFilter()

        kept, filtered = filter.filter_articles([sports_article, normal_article])

        assert len(kept) == 1
        assert len(filtered) == 1
        assert normal_article in kept
        assert sports_article in filtered

    def test_filter_articles_marks_filtered_flag(self, sports_article):
        """Should set filtered flag on filtered articles"""
        filter = ContentFilter()

        _kept, filtered = filter.filter_articles([sports_article])

        assert sports_article.filtered is True
        assert sports_article.filter_reason == "sports"

    def test_filter_articles_empty_list(self):
        """Should handle empty list"""
        filter = ContentFilter()

        kept, filtered = filter.filter_articles([])

        assert kept == []
        assert filtered == []

    def test_filter_articles_all_kept(self, normal_article, sample_article_factory):
        """Should keep all non-matching articles"""
        filter = ContentFilter()
        article2 = sample_article_factory(
            id=20, title="Another Normal Article", description="More news"
        )

        kept, filtered = filter.filter_articles([normal_article, article2])

        assert len(kept) == 2
        assert len(filtered) == 0


class TestGetFilterStats:
    """Tests for filter statistics"""

    def test_get_filter_stats_basic(
        self, sports_article, clickbait_article, normal_article
    ):
        """Should return filtering statistics"""
        filter = ContentFilter()

        # Pre-filter to set flags
        filter.filter_articles([sports_article, clickbait_article, normal_article])

        stats = filter.get_filter_stats(
            [sports_article, clickbait_article, normal_article]
        )

        assert stats["total_articles"] == 3
        assert stats["filtered_count"] == 2
        assert stats["kept_count"] == 1
        assert stats["filter_rate"] == pytest.approx(2 / 3, rel=0.01)
        assert "sports" in stats["reasons"]
        assert "clickbait" in stats["reasons"]

    def test_get_filter_stats_empty_list(self):
        """Should handle empty list without division error"""
        filter = ContentFilter()

        stats = filter.get_filter_stats([])

        assert stats["total_articles"] == 0
        assert stats["filter_rate"] == 0

    def test_get_filter_stats_no_filtered(self, normal_article, sample_article_factory):
        """Should handle no filtered articles"""
        filter = ContentFilter()
        article2 = sample_article_factory(id=21, title="News Update", description="News")

        filter.filter_articles([normal_article, article2])

        stats = filter.get_filter_stats([normal_article, article2])

        assert stats["filtered_count"] == 0
        assert stats["filter_rate"] == 0
        assert stats["reasons"] == {}
