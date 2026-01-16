"""
Maintenance-specific test fixtures
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_old_article():
    """Sample old article for retention testing"""
    article = MagicMock()
    article.id = 1
    article.fetched_at = datetime.utcnow() - timedelta(days=100)  # Old article
    article.title = "Old Article"
    return article


@pytest.fixture
def sample_recent_article():
    """Sample recent article for retention testing"""
    article = MagicMock()
    article.id = 2
    article.fetched_at = datetime.utcnow() - timedelta(days=10)  # Recent article
    article.title = "Recent Article"
    return article


@pytest.fixture
def sample_old_synthesis():
    """Sample old synthesis for retention testing"""
    synthesis = MagicMock()
    synthesis.id = 1
    synthesis.generated_at = datetime.utcnow() - timedelta(days=200)  # Old synthesis
    synthesis.executive_summary = "Old summary"
    return synthesis


@pytest.fixture
def sample_recent_synthesis():
    """Sample recent synthesis for retention testing"""
    synthesis = MagicMock()
    synthesis.id = 2
    synthesis.generated_at = datetime.utcnow() - timedelta(days=30)  # Recent synthesis
    synthesis.executive_summary = "Recent summary"
    return synthesis


@pytest.fixture
def mock_retention_settings(monkeypatch):
    """Mock retention settings"""
    mock = MagicMock()
    mock.retention_articles_days = 90
    mock.retention_syntheses_days = 180
    mock.retention_feed_health_days = 30
    monkeypatch.setattr("src.maintenance.data_retention.settings", mock)
    return mock
