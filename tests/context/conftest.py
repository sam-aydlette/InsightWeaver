"""
Context-specific test fixtures
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_user_profile():
    """Mock UserProfile for context testing"""
    profile = MagicMock()
    profile.profile = {
        "geographic_context": {
            "primary_location": {
                "city": "Fairfax",
                "state": "Virginia",
                "region": "Northern Virginia",
                "country": "USA",
            }
        },
        "professional_context": {
            "professional_domains": ["cybersecurity", "software development"]
        },
        "civic_interests": {"policy_areas": ["education", "housing"]},
        "briefing_preferences": {"perspective": "daily_intelligence_brief"},
    }
    profile.get_primary_location.return_value = {
        "city": "Fairfax",
        "state": "Virginia",
        "region": "Northern Virginia",
        "country": "USA",
    }
    profile.get_professional_domains.return_value = [
        "cybersecurity",
        "software development",
    ]
    profile.get_civic_interests.return_value = {"policy_areas": ["education", "housing"]}
    profile.get_professional_context.return_value = {
        "professional_domains": ["cybersecurity", "software development"]
    }
    profile.get_excluded_topics.return_value = []
    return profile


@pytest.fixture
def sample_article_for_context():
    """Sample article object for context testing"""

    def create_article(
        id=1,
        title="Test Article",
        description="Test description",
        normalized_content="Test content for the article",
        embedding_summary=None,
        published_date=None,
        url="https://example.com/article",
        entities=None,
        feed=None,
    ):
        article = MagicMock()
        article.id = id
        article.title = title
        article.description = description
        article.normalized_content = normalized_content
        article.embedding_summary = embedding_summary
        article.published_date = published_date or datetime.utcnow()
        article.url = url
        article.entities = entities or []
        article.feed = feed
        return article

    return create_article


@pytest.fixture
def sample_feed():
    """Sample feed object"""
    feed = MagicMock()
    feed.id = 1
    feed.name = "Test Feed"
    feed.category = "cybersecurity"
    return feed


@pytest.fixture
def sample_synthesis_data():
    """Sample synthesis data structure"""
    return {
        "bottom_line": {
            "summary": "Test summary with key findings.",
            "immediate_actions": ["Action 1", "Action 2"],
            "article_citations": [1, 2, 3],
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
            "national": [],
            "global": [],
            "niche_field": [],
        },
        "priority_events": [
            {
                "event": "City council meeting^[2]",
                "when": "Next Tuesday",
                "impact_level": "HIGH",
                "why_matters": "Policy changes expected^[2]",
                "recommended_action": "Attend the meeting",
                "confidence": 0.9,
                "article_citations": [2],
            }
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
            "generated_at": datetime.utcnow().isoformat(),
            "citation_map": {},
        },
    }


@pytest.fixture
def sample_context():
    """Sample curated context for synthesis"""
    return {
        "user_profile": {
            "location": "Fairfax, Virginia",
            "professional_domains": ["cybersecurity", "software development"],
            "civic_interests": ["education", "housing"],
        },
        "decision_context": "",
        "articles": [
            {
                "id": 1,
                "title": "Test Article 1",
                "source": "Test Feed",
                "published_date": datetime.utcnow().isoformat(),
                "content": "Content 1",
                "url": "https://example.com/1",
                "entities": [],
            },
            {
                "id": 2,
                "title": "Test Article 2",
                "source": "Test Feed",
                "published_date": datetime.utcnow().isoformat(),
                "content": "Content 2",
                "url": "https://example.com/2",
                "entities": [],
            },
        ],
        "perception": "",
        "anomaly_analysis": "",
        "memory": "No historical context available.",
        "instructions": "Test instructions",
    }


@pytest.fixture
def mock_narrative_synthesis():
    """Mock NarrativeSynthesis database object"""
    synthesis = MagicMock()
    synthesis.id = 1
    synthesis.generated_at = datetime.utcnow() - timedelta(days=1)
    synthesis.executive_summary = "Previous synthesis summary"
    synthesis.synthesis_data = {
        "bottom_line": {"summary": "Previous bottom line"},
        "trends_and_patterns": {},
        "priority_events": [],
        "predictions_scenarios": {},
    }
    return synthesis


@pytest.fixture
def mock_claude_response():
    """Mock Claude API response for synthesis"""
    return """{
    "bottom_line": {
        "summary": "Test synthesis summary",
        "immediate_actions": ["Action 1"],
        "article_citations": [1]
    },
    "trends_and_patterns": {
        "local": [],
        "state_regional": [],
        "national": [],
        "global": [],
        "niche_field": []
    },
    "priority_events": [],
    "predictions_scenarios": {
        "local_governance": [],
        "education": [],
        "niche_field": [],
        "economic_conditions": [],
        "infrastructure": []
    },
    "metadata": {
        "articles_analyzed": 5,
        "generated_at": "2024-01-15T12:00:00"
    }
}"""
