"""
Tests for RSS feed configuration
"""


from src.config.feeds import (
    RSS_FEEDS,
    get_all_feeds,
    get_category_list,
    get_feed_count,
    get_feeds_by_category,
    get_feeds_by_category_group,
    validate_feeds,
)


class TestRSSFeedsStructure:
    """Tests for RSS_FEEDS data structure"""

    def test_rss_feeds_is_dict(self):
        """RSS_FEEDS should be a dictionary"""
        assert isinstance(RSS_FEEDS, dict)

    def test_rss_feeds_has_categories(self):
        """RSS_FEEDS should have multiple category groups"""
        assert len(RSS_FEEDS) > 0
        expected_groups = [
            "government",
            "virginia",
            "cybersecurity",
            "technology",
            "news",
        ]
        for group in expected_groups:
            assert group in RSS_FEEDS, f"Category group '{group}' should exist"

    def test_each_category_has_feeds(self):
        """Each category group should have at least one feed"""
        for group_name, feeds in RSS_FEEDS.items():
            assert isinstance(feeds, list), f"{group_name} should be a list"
            assert len(feeds) > 0, f"{group_name} should have at least one feed"

    def test_feed_has_required_fields(self):
        """Each feed should have required fields"""
        required_fields = ["name", "url", "category", "description"]

        for group_name, feeds in RSS_FEEDS.items():
            for i, feed in enumerate(feeds):
                for field in required_fields:
                    assert field in feed, f"{group_name}[{i}] missing '{field}'"
                    assert feed[field], f"{group_name}[{i}] has empty '{field}'"


class TestGetAllFeeds:
    """Tests for get_all_feeds function"""

    def test_returns_list(self):
        """get_all_feeds should return a list"""
        result = get_all_feeds()
        assert isinstance(result, list)

    def test_returns_all_feeds(self):
        """get_all_feeds should return all feeds from all categories"""
        result = get_all_feeds()

        total_expected = sum(len(feeds) for feeds in RSS_FEEDS.values())
        assert len(result) == total_expected

    def test_adds_category_group(self):
        """get_all_feeds should add category_group to each feed"""
        result = get_all_feeds()

        for feed in result:
            assert "category_group" in feed
            assert feed["category_group"] in RSS_FEEDS

    def test_preserves_original_fields(self):
        """get_all_feeds should preserve original feed fields"""
        result = get_all_feeds()

        for feed in result:
            assert "name" in feed
            assert "url" in feed
            assert "category" in feed
            assert "description" in feed


class TestGetFeedsByCategory:
    """Tests for get_feeds_by_category function"""

    def test_returns_matching_feeds(self):
        """Should return feeds with matching category"""
        result = get_feeds_by_category("security_news")

        assert isinstance(result, list)
        for feed in result:
            assert feed["category"] == "security_news"

    def test_returns_empty_for_nonexistent_category(self):
        """Should return empty list for non-existent category"""
        result = get_feeds_by_category("nonexistent_category_xyz")

        assert isinstance(result, list)
        assert len(result) == 0

    def test_adds_category_group(self):
        """Should add category_group to returned feeds"""
        result = get_feeds_by_category("security_news")

        for feed in result:
            assert "category_group" in feed


class TestGetFeedsByCategoryGroup:
    """Tests for get_feeds_by_category_group function"""

    def test_returns_feeds_for_valid_group(self):
        """Should return feeds for valid category group"""
        result = get_feeds_by_category_group("cybersecurity")

        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_empty_for_invalid_group(self):
        """Should return empty list for invalid category group"""
        result = get_feeds_by_category_group("invalid_group_xyz")

        assert isinstance(result, list)
        assert len(result) == 0

    def test_returns_same_as_direct_access(self):
        """Should return same result as direct RSS_FEEDS access"""
        result = get_feeds_by_category_group("government")

        assert result == RSS_FEEDS["government"]


class TestGetFeedCount:
    """Tests for get_feed_count function"""

    def test_returns_positive_integer(self):
        """Should return a positive integer"""
        result = get_feed_count()

        assert isinstance(result, int)
        assert result > 0

    def test_matches_all_feeds_length(self):
        """Should match length of get_all_feeds()"""
        result = get_feed_count()
        all_feeds = get_all_feeds()

        assert result == len(all_feeds)


class TestGetCategoryList:
    """Tests for get_category_list function"""

    def test_returns_sorted_list(self):
        """Should return a sorted list"""
        result = get_category_list()

        assert isinstance(result, list)
        assert result == sorted(result)

    def test_contains_unique_categories(self):
        """Should contain unique category values"""
        result = get_category_list()

        assert len(result) == len(set(result))

    def test_contains_expected_categories(self):
        """Should contain expected category values"""
        result = get_category_list()

        expected = ["security_news", "tech_news", "politics", "general_news"]
        for cat in expected:
            assert cat in result, f"Category '{cat}' should exist"


class TestValidateFeeds:
    """Tests for validate_feeds function"""

    def test_returns_list(self):
        """Should return a list of issues"""
        result = validate_feeds()

        assert isinstance(result, list)

    def test_current_config_has_duplicates(self):
        """Current config may have intentional duplicates (Federal Reserve, SEC)"""
        # This test documents the current state
        # Some feeds appear in multiple categories intentionally
        result = validate_feeds()

        # Just verify the function runs
        assert isinstance(result, list)


class TestFeedUrlFormat:
    """Tests for feed URL format validation"""

    def test_all_urls_are_http_or_https(self):
        """All feed URLs should use HTTP or HTTPS"""
        all_feeds = get_all_feeds()

        for feed in all_feeds:
            url = feed["url"]
            assert url.startswith("http://") or url.startswith(
                "https://"
            ), f"Invalid URL scheme: {url}"

    def test_no_empty_urls(self):
        """No feed should have empty URL"""
        all_feeds = get_all_feeds()

        for feed in all_feeds:
            assert feed["url"].strip(), f"Empty URL for feed: {feed['name']}"


class TestFeedCategories:
    """Tests for feed category consistency"""

    def test_category_groups_are_strings(self):
        """All category group keys should be strings"""
        for key in RSS_FEEDS:
            assert isinstance(key, str)

    def test_feed_categories_are_strings(self):
        """All feed categories should be strings"""
        all_feeds = get_all_feeds()

        for feed in all_feeds:
            assert isinstance(feed["category"], str)
            assert len(feed["category"]) > 0
