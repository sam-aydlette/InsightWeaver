"""
Unit tests for ContentFilter
"""

import unittest
from src.processors.content_filter import ContentFilter


class TestContentFilter(unittest.TestCase):
    """Test ContentFilter sports/clickbait detection"""

    def setUp(self):
        """Create filter without user profile for basic testing"""
        self.filter = ContentFilter()

    def test_sports_detection(self):
        """Test detection of sports content"""
        title = "NFL playoffs quarterback touchdown Super Bowl"
        should_filter, reason = self.filter.should_filter(title)

        self.assertTrue(should_filter)
        self.assertEqual(reason, "sports")

    def test_clickbait_detection_keywords(self):
        """Test detection of clickbait keywords"""
        title = "You won't believe what happens next! Shocking discovery!"
        should_filter, reason = self.filter.should_filter(title)

        self.assertTrue(should_filter)
        self.assertEqual(reason, "clickbait")

    def test_clickbait_detection_punctuation(self):
        """Test detection of clickbait through excessive punctuation"""
        title = "Breaking news!!! Amazing results!!!"
        should_filter, reason = self.filter.should_filter(title)

        self.assertTrue(should_filter)
        self.assertEqual(reason, "clickbait")

    def test_entertainment_detection(self):
        """Test detection of entertainment content"""
        title = "Celebrity red carpet fashion at the Oscars"
        should_filter, reason = self.filter.should_filter(title)

        self.assertTrue(should_filter)
        self.assertEqual(reason, "entertainment")

    def test_legitimate_news_passes(self):
        """Test that legitimate news passes through"""
        title = "Federal government announces new AI regulation policy"
        should_filter, reason = self.filter.should_filter(title)

        self.assertFalse(should_filter)
        self.assertIsNone(reason)

    def test_technology_news_passes(self):
        """Test that technology news passes through"""
        title = "New cybersecurity framework released for federal agencies"
        description = "The framework addresses cloud security and zero trust architecture"
        should_filter, reason = self.filter.should_filter(title, description)

        self.assertFalse(should_filter)
        self.assertIsNone(reason)

    def test_single_sports_keyword_passes(self):
        """Test that single sports keyword doesn't trigger filter (needs 2+)"""
        title = "The game changing strategy for business success"
        should_filter, reason = self.filter.should_filter(title)

        self.assertFalse(should_filter)
        self.assertIsNone(reason)

    def test_user_excluded_topics(self):
        """Test filtering based on user profile excluded topics"""
        # Create mock user profile
        class MockProfile:
            def get_excluded_topics(self):
                return ["cryptocurrency", "blockchain"]

        filter_with_profile = ContentFilter(MockProfile())

        title = "Bitcoin and blockchain technology surge in markets"
        should_filter, reason = self.filter.should_filter(title)

        # Without profile this passes
        self.assertFalse(should_filter)

        # With profile this filters
        should_filter, reason = filter_with_profile.should_filter(title)
        self.assertTrue(should_filter)
        self.assertIn("excluded_topic", reason)


if __name__ == '__main__':
    unittest.main()