"""
Pipeline-specific test fixtures
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for pipeline tests"""
    monkeypatch.setattr("src.pipeline.orchestrator.settings.anthropic_api_key", "test-key")
    monkeypatch.setattr(
        "src.pipeline.orchestrator.settings.enable_smart_rss_fetch", True
    )
    monkeypatch.setattr(
        "src.pipeline.orchestrator.settings.smart_rss_fetch_threshold_minutes", 60
    )
    monkeypatch.setattr(
        "src.pipeline.orchestrator.settings.enable_trust_verification", True
    )


@pytest.fixture
def sample_fetch_results():
    """Sample RSS fetch results"""
    return {
        "total_feeds": 10,
        "successful_feeds": 8,
        "failed_feeds": 2,
        "total_articles": 50,
        "new_articles": 30,
        "duplicate_articles": 20,
        "error_summary": {"Network error": 1, "Parse error": 1},
    }


@pytest.fixture
def sample_dedup_results():
    """Sample deduplication results"""
    return {
        "total_duplicates": 15,
        "exact_duplicates": 10,
        "semantic_duplicates": 5,
        "articles_processed": 100,
    }


@pytest.fixture
def sample_filter_results():
    """Sample content filtering results"""
    return {
        "articles_evaluated": 100,
        "filtered_count": 25,
        "kept_count": 75,
        "filter_rate": 0.25,
        "reasons": {
            "sports_content": 10,
            "entertainment": 8,
            "clickbait": 7,
        },
    }


@pytest.fixture
def sample_synthesis_results():
    """Sample synthesis results"""
    return {
        "synthesis_id": 123,
        "articles_analyzed": 50,
        "executive_summary": "Test summary",
        "synthesis_data": {
            "bottom_line": {"summary": "Test bottom line"},
            "trends_and_patterns": {"local": []},
            "priority_events": [],
            "predictions_scenarios": {},
        },
    }


@pytest.fixture
def sample_pipeline_results(
    sample_fetch_results, sample_dedup_results, sample_filter_results, sample_synthesis_results
):
    """Sample complete pipeline results"""
    return {
        "pipeline_started": datetime.now(UTC).isoformat(),
        "pipeline_completed": datetime.now(UTC).isoformat(),
        "stages": {
            "fetch": sample_fetch_results,
            "deduplication": sample_dedup_results,
            "filtering": sample_filter_results,
            "synthesis": sample_synthesis_results,
        },
        "summary": {
            "total_stages_run": 4,
            "feeds_processed": 10,
            "articles_fetched": 50,
            "duplicates_removed": 15,
            "articles_filtered": 25,
            "articles_kept": 75,
            "articles_synthesized": 50,
            "narrative_generated": True,
            "duration_seconds": 30.5,
        },
    }


@pytest.fixture
def mock_article_with_fetch_time():
    """Mock article with recent fetch time"""
    article = MagicMock()
    article.fetched_at = datetime.now(UTC) - timedelta(minutes=30)
    return article


@pytest.fixture
def mock_article_with_old_fetch_time():
    """Mock article with old fetch time"""
    article = MagicMock()
    article.fetched_at = datetime.now(UTC) - timedelta(hours=2)
    return article


@pytest.fixture
def mock_user_profile_for_pipeline():
    """Mock user profile for pipeline tests"""
    profile = MagicMock()
    profile.get_primary_location.return_value = {
        "city": "Fairfax",
        "state": "Virginia",
    }
    profile.get_professional_domains.return_value = ["cybersecurity"]
    profile.get_civic_interests.return_value = {"policy_areas": ["education"]}
    profile.get_excluded_topics.return_value = []
    return profile
