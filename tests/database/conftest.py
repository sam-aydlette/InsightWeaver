"""
Database-specific test fixtures
Provides in-memory SQLite database and sample model instances
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    AnalysisRun,
    APIDataPoint,
    APIDataSource,
    Article,
    Base,
    CausalChain,
    ContextSnapshot,
    ForecastRun,
    ForecastScenario,
    LongTermForecast,
    MemoryFact,
    MonitoredPage,
    NarrativeSynthesis,
    PageChange,
    RSSFeed,
)


@pytest.fixture
def test_engine(tmp_path):
    """Create in-memory SQLite database for testing"""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Database session for tests"""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


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
        claude_model="claude-3-5-sonnet",
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
def sample_api_data_source(test_session):
    """Create a sample APIDataSource for testing"""
    source = APIDataSource(
        name="Test API Source",
        source_type="calendar",
        endpoint_url="https://api.example.com/events",
        api_key_required=False,
        refresh_frequency_hours=24,
        is_active=True,
    )
    test_session.add(source)
    test_session.commit()
    return source


@pytest.fixture
def sample_api_data_point(test_session, sample_api_data_source):
    """Create a sample APIDataPoint for testing"""
    data_point = APIDataPoint(
        source_id=sample_api_data_source.id,
        data_type="event",
        external_id="event-123",
        title="Test Event",
        description="Test event description",
        data_payload={"location": "Test Location", "time": "10:00 AM"},
        event_date=datetime.utcnow() + timedelta(days=7),
        relevance_score=0.75,
    )
    test_session.add(data_point)
    test_session.commit()
    return data_point


@pytest.fixture
def sample_monitored_page(test_session):
    """Create a sample MonitoredPage for testing"""
    page = MonitoredPage(
        url="https://example.gov/policy",
        name="Policy Page",
        page_type="policy",
        selector=".content-main",
        check_frequency_hours=12,
        is_active=True,
    )
    test_session.add(page)
    test_session.commit()
    return page


@pytest.fixture
def sample_page_change(test_session, sample_monitored_page):
    """Create a sample PageChange for testing"""
    change = PageChange(
        monitored_page_id=sample_monitored_page.id,
        change_type="content_modified",
        old_content="Old policy text",
        new_content="New policy text with updates",
        diff_summary="Policy updated with new requirements",
        content_hash="newhash123",
        relevance_score=0.9,
    )
    test_session.add(change)
    test_session.commit()
    return change


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
        data_sources_used=["RSS feeds", "API data"],
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
