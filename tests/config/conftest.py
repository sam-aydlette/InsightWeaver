"""
Config-specific test fixtures
"""

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """Clear environment variables that might affect settings"""
    env_vars = [
        "DATABASE_URL",
        "ANTHROPIC_API_KEY",
        "DEBUG",
        "LOG_LEVEL",
        "ENABLE_SMART_RSS_FETCH",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture
def sample_feed_config():
    """Sample feed configuration for testing"""
    return {
        "name": "Test Feed",
        "url": "https://example.com/feed.xml",
        "category": "test_category",
        "description": "A test feed for testing purposes",
    }
