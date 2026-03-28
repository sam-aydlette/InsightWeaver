"""
Shared test fixtures for all InsightWeaver tests
Provides mocks for ClaudeClient, web_fetch, and common test data
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base


@pytest.fixture
def test_engine(tmp_path):
    """Create temporary SQLite database with all tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Database session for tests."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_claude_client(mocker):
    """
    Mock ClaudeClient for all tests

    Returns an AsyncMock that can be configured per test to return
    specific JSON responses from the analyze() method.
    """
    mock_client = mocker.AsyncMock()
    mock_client.analyze = mocker.AsyncMock()
    return mock_client


@pytest.fixture
def mock_web_fetch(mocker):
    """
    Mock web_fetch for authoritative source testing

    Returns an AsyncMock that can be configured to return specific
    content from web sources without making real HTTP requests.
    """
    mock_fetch = mocker.patch("src.utils.web_tools.web_fetch", new_callable=mocker.AsyncMock)
    return mock_fetch


@pytest.fixture
def mock_authoritative_sources():
    """
    Mock authoritative_sources.yaml config

    Returns a dictionary mimicking the YAML structure with test sources.
    """
    return {
        "sources": [
            {
                "name": "Test US President Source",
                "keywords": ["president", "united states", "potus"],
                "url": "https://test.whitehouse.gov/administration/president",
                "query_prompt": "Who is the current president of the United States?",
            },
            {
                "name": "Test Prime Minister India",
                "keywords": ["prime minister", "india"],
                "url": "https://test.pmindia.gov.in",
                "query_prompt": "Who is the current Prime Minister of India?",
            },
            {
                "name": "Test CEO Apple",
                "keywords": ["ceo", "apple", "leadership"],
                "url": "https://test.apple.com/leadership",
                "query_prompt": "Who is the current CEO of Apple?",
            },
            {
                "name": "Test Unemployment Rate",
                "keywords": ["unemployment", "rate", "labor", "jobs"],
                "url": "https://test.bls.gov/unemployment",
                "query_prompt": "What is the current unemployment rate?",
            },
            {
                "name": "Test Wikipedia Country Template",
                "keywords": ["country", "wikipedia"],
                "url_template": "https://en.wikipedia.org/wiki/{country}",
                "requires_country_extraction": True,
                "query_prompt": "Extract information about the country from Wikipedia",
            },
        ],
        "fallback": {
            "enabled": True,
            "reason": "No authoritative source available for verification beyond model knowledge cutoff",
        },
    }


@pytest.fixture
def sample_response():
    """
    Sample Claude response with various claim types for testing
    """
    return """The unemployment rate is 3.7% as of December 2025. This suggests a strong labor market.
    It's possible that rates will remain low through 2026. Many economists believe the economy is healthy."""


@pytest.fixture
def mock_settings(monkeypatch):
    """
    Mock settings for testing without requiring .env file
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    return None


@pytest.fixture
def temp_yaml_file(tmp_path, mock_authoritative_sources):
    """
    Create a temporary YAML file with mock sources for testing
    """
    import yaml

    yaml_path = tmp_path / "authoritative_sources.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(mock_authoritative_sources, f)
    return yaml_path
