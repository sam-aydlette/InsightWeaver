"""
Newsletter-specific test fixtures
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_synthesis_data_for_newsletter():
    """Sample synthesis data structure for newsletter tests"""
    return {
        "bottom_line": {
            "summary": "Test summary with important findings.^[1]",
            "immediate_actions": ["Action 1^[1]", "Action 2^[2]"],
            "article_citations": [1, 2],
        },
        "trends_and_patterns": {
            "local": [
                {
                    "subject": "Local cybersecurity^[1]",
                    "direction": "increasing",
                    "quantifier": "15%^[1]",
                    "description": "Trend description^[1]",
                    "confidence": 0.85,
                    "article_citations": [1],
                }
            ],
            "state_regional": [],
            "national": [
                {
                    "subject": "Federal policy^[2]",
                    "direction": "changing",
                    "quantifier": "",
                    "description": "Policy updates^[2]",
                    "confidence": 0.75,
                    "article_citations": [2],
                }
            ],
            "global": [],
            "niche_field": [],
        },
        "priority_events": [
            {
                "event": "City council meeting^[3]",
                "when": "Next Tuesday",
                "impact_level": "HIGH",
                "why_matters": "Budget decisions^[3]",
                "recommended_action": "Attend the meeting",
                "confidence": 0.9,
                "article_citations": [3],
            },
            {
                "event": "School board hearing^[4]",
                "when": "Next Thursday",
                "impact_level": "MEDIUM",
                "why_matters": "Curriculum changes^[4]",
                "recommended_action": "Submit public comment",
                "confidence": 0.85,
                "article_citations": [4],
            },
        ],
        "predictions_scenarios": {
            "local_governance": [
                {
                    "prediction": "Budget increase likely^[3]",
                    "confidence": 0.75,
                    "timeframe": "2-4 weeks",
                    "rationale": "Based on council discussions^[3]",
                    "article_citations": [3],
                }
            ],
            "education": [],
            "niche_field": [],
            "economic_conditions": [],
            "infrastructure": [],
        },
        "metadata": {
            "articles_analyzed": 10,
            "generated_at": datetime.now().isoformat(),
            "synthesis_id": "abc123def456",
            "citation_map": {
                "1": {
                    "title": "Test Article 1",
                    "source": "Test Source",
                    "url": "https://example.com/1",
                },
                "2": {
                    "title": "Test Article 2",
                    "source": "Test Source",
                    "url": "https://example.com/2",
                },
                "3": {
                    "title": "City Council Article",
                    "source": "Local News",
                    "url": "https://example.com/3",
                },
                "4": {
                    "title": "School Board Article",
                    "source": "Education News",
                    "url": "https://example.com/4",
                },
            },
        },
    }


@pytest.fixture
def sample_content_data(sample_synthesis_data_for_newsletter):
    """Sample content data for newsletter generation"""
    return {
        "start_date": datetime.now() - timedelta(hours=24),
        "end_date": datetime.now(),
        "duration_hours": 24,
        "report_type": "daily",
        "synthesis_data": sample_synthesis_data_for_newsletter,
        "executive_summary": "Test executive summary for the daily brief.",
        "articles_analyzed": 10,
        "user_context": {
            "location": {"city": "Fairfax", "state": "Virginia"},
            "professional_domains": ["cybersecurity", "software development"],
        },
        "synthesis_id": 123,
        "processing_time": "5.0s",
        "trust_verification": {"passed": True, "issues": []},
    }


@pytest.fixture
def sample_weekly_content_data(sample_synthesis_data_for_newsletter):
    """Sample content data for weekly report"""
    return {
        "start_date": datetime.now() - timedelta(days=7),
        "end_date": datetime.now(),
        "duration_hours": 168,
        "report_type": "weekly",
        "synthesis_data": sample_synthesis_data_for_newsletter,
        "executive_summary": "Weekly summary of key developments.",
        "articles_analyzed": 50,
        "user_context": {
            "location": {"city": "Fairfax", "state": "Virginia"},
            "professional_domains": ["cybersecurity"],
        },
        "synthesis_id": 456,
        "processing_time": "15.0s",
    }


@pytest.fixture
def sample_empty_synthesis_data():
    """Empty synthesis data for testing empty reports"""
    return {
        "bottom_line": {},
        "trends_and_patterns": {
            "local": [],
            "state_regional": [],
            "national": [],
            "global": [],
            "niche_field": [],
        },
        "priority_events": [],
        "predictions_scenarios": {
            "local_governance": [],
            "education": [],
            "niche_field": [],
            "economic_conditions": [],
            "infrastructure": [],
        },
        "metadata": {
            "articles_analyzed": 0,
            "generated_at": datetime.now().isoformat(),
            "citation_map": {},
        },
    }


@pytest.fixture
def mock_email_sender():
    """Mock EmailSender for testing"""
    sender = MagicMock()
    sender.email_enabled = True
    sender.smtp_server = "smtp.gmail.com"
    sender.smtp_port = 587
    sender.from_email = "test@example.com"
    sender.email_username = "test_user"
    sender.email_password = "test_pass"
    return sender


@pytest.fixture
def mock_user_profile_for_newsletter():
    """Mock user profile for newsletter tests"""
    profile = MagicMock()
    profile.get_primary_location.return_value = {
        "city": "Fairfax",
        "state": "Virginia",
        "region": "Northern Virginia",
    }
    profile.get_professional_domains.return_value = ["cybersecurity", "software development"]
    profile.get_civic_interests.return_value = {"policy_areas": ["education", "housing"]}
    return profile


@pytest.fixture
def mock_narrative_synthesis():
    """Mock NarrativeSynthesis database object"""
    synthesis = MagicMock()
    synthesis.id = 123
    synthesis.generated_at = datetime.now() - timedelta(hours=1)
    synthesis.executive_summary = "Test executive summary"
    synthesis.articles_analyzed = 10
    synthesis.synthesis_data = {
        "bottom_line": {"summary": "Test bottom line"},
        "trends_and_patterns": {"local": [], "national": []},
        "priority_events": [],
        "predictions_scenarios": {"local_governance": []},
        "metadata": {"citation_map": {}},
    }
    return synthesis
