"""
Database-specific test fixtures.

Provides sample model instances for database tests. test_engine and
test_session are inherited from tests/conftest.py.

The sample_analysis_run / sample_context_snapshot / sample_narrative_synthesis
fixtures were removed by backlog task 012 along with the models they built.
"""

from datetime import datetime, timedelta

import pytest

from src.database.models import Article, RSSFeed


@pytest.fixture
def sample_rss_feed(test_session):
    """Create a sample RSSFeed for testing"""
    feed = RSSFeed(
        url="https://example.com/feed.xml",
        name="Test Feed",
        category="technology",
        is_active=True,
    )
    test_session.add(feed)
    test_session.commit()
    return feed


@pytest.fixture
def sample_article(test_session, sample_rss_feed):
    """Create a sample Article for testing"""
    article = Article(
        feed_id=sample_rss_feed.id,
        guid="test-guid-123",
        url="https://example.com/article",
        title="Test Article Title",
        description="Test article description",
        content="<p>Full article content here</p>",
        normalized_content="Full article content here",
        word_count=4,
        language="en",
        published_date=datetime.utcnow() - timedelta(hours=2),
        relevance_score=0.85,
        filtered=False,
    )
    test_session.add(article)
    test_session.commit()
    return article
