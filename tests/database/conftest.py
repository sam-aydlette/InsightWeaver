"""
Database-specific test fixtures
Provides sample model instances for database tests.
test_engine and test_session are inherited from tests/conftest.py.
"""

from datetime import datetime, timedelta

import pytest

from src.database.models import (
    AnalysisRun,
    Article,
    ContextSnapshot,
    NarrativeSynthesis,
    RSSFeed,
)


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


@pytest.fixture
def sample_analysis_run(test_session):
    """Create a sample AnalysisRun for testing"""
    run = AnalysisRun(
        run_type="narrative_synthesis",
        status="completed",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
        articles_processed=10,
        context_token_count=5000,
        claude_model="claude-sonnet-4-20250514",
    )
    test_session.add(run)
    test_session.commit()
    return run


@pytest.fixture
def sample_context_snapshot(test_session):
    """Create a sample ContextSnapshot for testing"""
    snapshot = ContextSnapshot(
        synthesis_id=None,
        article_ids=[1, 2, 3],
        context_size_tokens=5000,
        user_profile_hash="abc123def456",
        historical_summaries="Previous analysis summary",
        instructions="Generate narrative synthesis",
    )
    test_session.add(snapshot)
    test_session.commit()
    return snapshot


@pytest.fixture
def sample_narrative_synthesis(test_session, sample_analysis_run, sample_context_snapshot):
    """Create a sample NarrativeSynthesis for testing"""
    synthesis = NarrativeSynthesis(
        analysis_run_id=sample_analysis_run.id,
        context_snapshot_id=sample_context_snapshot.id,
        user_profile_version="1.0",
        synthesis_data={"bottom_line": {"summary": "Test summary"}},
        executive_summary="Executive summary text",
        articles_analyzed=10,
        temporal_scope="immediate,near,medium",
    )
    test_session.add(synthesis)
    test_session.commit()
    return synthesis
