"""
Monitoring-specific test fixtures
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_health_settings(monkeypatch):
    """Mock settings for health monitoring"""
    mock = MagicMock()
    mock.database_url = "sqlite:///test.db"
    mock.data_dir = MagicMock()
    mock.data_dir.rglob.return_value = []
    mock.retention_articles_days = 90
    mock.retention_syntheses_days = 180
    monkeypatch.setattr("src.monitoring.health_monitor.settings", mock)
    return mock


@pytest.fixture
def sample_feed_health():
    """Sample feed health data"""
    return {
        "status": "healthy",
        "total_feeds": 20,
        "active_feeds": 18,
        "feeds_with_errors": 2,
        "stale_feeds": 1,
        "issues": [],
    }


@pytest.fixture
def sample_synthesis_health():
    """Sample synthesis health data"""
    return {
        "status": "healthy",
        "recent_syntheses_7d": 7,
        "latest_synthesis": datetime.utcnow().isoformat(),
        "hours_since_last": 2.5,
        "issues": [],
    }


@pytest.fixture
def sample_memory_health():
    """Sample memory system health data"""
    return {
        "status": "healthy",
        "total_facts": 100,
        "active_facts": 95,
        "expired_facts": 5,
        "facts_by_type": {"trend": 50, "event": 30, "entity": 20},
    }


@pytest.fixture
def sample_performance_metrics():
    """Sample performance metrics"""
    return {
        "period_days": 7,
        "articles_collected": 500,
        "articles_per_day": 71.4,
        "syntheses_generated": 7,
        "facts_created": 50,
    }
