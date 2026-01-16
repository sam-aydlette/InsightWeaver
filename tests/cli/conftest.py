"""
CLI-specific test fixtures
"""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Click CLI test runner"""
    return CliRunner()


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for CLI tests"""
    monkeypatch.setattr("src.cli.app.settings", MagicMock())
    monkeypatch.setattr("src.cli.brief.settings", MagicMock())
    monkeypatch.setattr("src.cli.trust.settings", MagicMock())
    monkeypatch.setattr("src.cli.forecast.settings", MagicMock())


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock API key as configured"""
    mock = MagicMock()
    mock.anthropic_api_key = "test-api-key"
    monkeypatch.setattr("src.cli.trust.settings", mock)
    monkeypatch.setattr("src.cli.brief.settings", mock)


@pytest.fixture
def mock_no_api_key(monkeypatch):
    """Mock API key as not configured"""
    mock = MagicMock()
    mock.anthropic_api_key = None
    monkeypatch.setattr("src.cli.trust.settings", mock)
    monkeypatch.setattr("src.cli.brief.settings", mock)


@pytest.fixture
def sample_brief_result():
    """Sample brief command result"""
    return {
        "success": True,
        "articles_analyzed": 10,
        "report_type": "daily",
        "local_saved": True,
        "local_path": "/tmp/report.html",
        "synthesis_data": {
            "bottom_line": {"summary": "Test summary"},
            "trends_and_patterns": {"local": []},
            "priority_events": [],
        },
    }


@pytest.fixture
def sample_trust_result():
    """Sample trust command result"""
    return {
        "response": "This is the AI response to the query.",
        "analysis": {
            "fact_verification": {
                "claims": [],
                "verified_count": 0,
                "unverified_count": 0,
                "accuracy_score": 1.0,
            },
            "bias_analysis": {
                "bias_detected": False,
                "bias_indicators": [],
                "neutrality_score": 0.95,
            },
            "tone_analysis": {
                "tone": "professional",
                "intimacy_level": "appropriate",
                "issues": [],
            },
            "overall_trust_score": 0.9,
        },
        "metadata": {
            "query": "Test query",
            "timestamp": "2024-01-15T12:00:00",
            "verification_performed": True,
        },
    }


@pytest.fixture
def sample_forecast_result():
    """Sample forecast command result"""
    return {
        "success": True,
        "horizons": {
            "6mo": {
                "executive_summary": "Short-term outlook is stable",
                "key_trends": ["Trend 1", "Trend 2"],
            },
            "1yr": {
                "executive_summary": "Medium-term shows growth potential",
                "key_trends": ["Trend 3"],
            },
        },
        "scenarios": [],
        "metadata": {
            "generated_at": "2024-01-15T12:00:00",
            "articles_analyzed": 50,
        },
    }
