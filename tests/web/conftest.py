"""
Web-specific test fixtures
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def flask_app():
    """Flask application for testing"""
    from src.web.server import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def test_client(flask_app):
    """Flask test client"""
    return flask_app.test_client()


@pytest.fixture
def sample_brief_data():
    """Sample brief data for web tests"""
    return {
        "success": True,
        "articles_analyzed": 10,
        "report_type": "daily",
        "synthesis_data": {
            "bottom_line": {"summary": "Test summary"},
            "trends_and_patterns": {"local": []},
            "priority_events": [],
        },
    }


@pytest.fixture
def sample_forecast_data():
    """Sample forecast data for web tests"""
    return {
        "success": True,
        "horizons": {
            "6mo": {"executive_summary": "Short-term outlook"},
            "1yr": {"executive_summary": "Medium-term outlook"},
        },
    }


@pytest.fixture
def sample_trust_data():
    """Sample trust data for web tests"""
    return {
        "response": "AI response",
        "analysis": {
            "overall_trust_score": 0.9,
            "fact_verification": {"accuracy_score": 0.95},
            "bias_analysis": {"neutrality_score": 0.85},
        },
    }


@pytest.fixture
def mock_newsletter_system():
    """Mock NewsletterSystem for web tests"""
    mock = MagicMock()
    mock.generate_report.return_value = {
        "success": True,
        "articles_analyzed": 10,
    }
    return mock


@pytest.fixture
def mock_trust_pipeline():
    """Mock TrustPipeline for web tests"""
    mock = MagicMock()
    mock.run_full_pipeline.return_value = {
        "response": "Test response",
        "analysis": {},
    }
    return mock
