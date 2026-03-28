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
    CausalChain,
    ContextSnapshot,
    ForecastRun,
    ForecastScenario,
    LongTermForecast,
    MemoryFact,
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


@pytest.fixture
def sample_memory_fact(test_session, sample_narrative_synthesis):
    """Create a sample MemoryFact for testing"""
    fact = MemoryFact(
        fact_type="metric",
        subject="Fairfax County unemployment",
        predicate="rate",
        object="2.3%",
        temporal_context="January 2026",
        confidence=0.85,
        source_synthesis_id=sample_narrative_synthesis.id,
    )
    test_session.add(fact)
    test_session.commit()
    return fact


@pytest.fixture
def sample_forecast_run(test_session):
    """Create a sample ForecastRun for testing"""
    run = ForecastRun(
        run_type="multi_horizon",
        horizons_requested=["6mo", "1yr", "3yr"],
        scenario_count=3,
        status="completed",
        started_at=datetime.utcnow() - timedelta(minutes=10),
        completed_at=datetime.utcnow(),
        forecasts_generated=3,
    )
    test_session.add(run)
    test_session.commit()
    return run


@pytest.fixture
def sample_long_term_forecast(test_session, sample_forecast_run):
    """Create a sample LongTermForecast for testing"""
    forecast = LongTermForecast(
        forecast_run_id=sample_forecast_run.id,
        time_horizon="1yr",
        horizon_months=12,
        base_date=datetime.utcnow(),
        target_date=datetime.utcnow() + timedelta(days=365),
        forecast_data={
            "trend_extrapolations": [],
            "scenarios": [],
            "historical_patterns": [],
            "causal_chains": [],
            "event_risks": {},
        },
        data_sources_used=["RSS feeds"],
        articles_analyzed=50,
        historical_months_analyzed=6,
        context_tokens=10000,
        generation_tokens=2000,
    )
    test_session.add(forecast)
    test_session.commit()
    return forecast


@pytest.fixture
def sample_forecast_scenario(test_session, sample_long_term_forecast):
    """Create a sample ForecastScenario for testing"""
    scenario = ForecastScenario(
        forecast_id=sample_long_term_forecast.id,
        scenario_type="baseline",
        scenario_name="Baseline Scenario",
        scenario_description="Most likely outcome based on current trends",
        predictions={"economic_growth": "2.5%", "unemployment": "4.0%"},
        key_assumptions=["No major policy changes", "Stable global economy"],
        trigger_events=["GDP reports", "Fed announcements"],
        scenario_probability=0.5,
    )
    test_session.add(scenario)
    test_session.commit()
    return scenario


@pytest.fixture
def sample_causal_chain(test_session, sample_long_term_forecast):
    """Create a sample CausalChain for testing"""
    chain = CausalChain(
        forecast_id=sample_long_term_forecast.id,
        chain_name="Interest Rate Impact",
        initial_cause="Fed raises interest rates",
        intermediate_effects=[
            "Higher borrowing costs",
            "Reduced consumer spending",
            "Business investment slowdown",
        ],
        final_outcome="Economic growth moderation",
        time_to_unfold_months=6,
        confidence=0.7,
    )
    test_session.add(chain)
    test_session.commit()
    return chain
