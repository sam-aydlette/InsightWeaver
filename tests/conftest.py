"""
Shared test fixtures for all InsightWeaver tests
Provides mocks for ClaudeClient, web_fetch, and common test data
"""

import pytest


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
def sample_claims():
    """
    Sample Claim objects for testing
    """
    from src.trust.fact_verifier import Claim

    return [
        Claim("The unemployment rate is 3.7%", "FACT", 0.9, "Specific quantitative claim"),
        Claim(
            "This suggests a strong labor market", "INFERENCE", 0.7, "Logical conclusion from data"
        ),
        Claim("Rates will remain low", "SPECULATION", 0.5, "Prediction without evidence"),
        Claim("The economy is healthy", "OPINION", 0.6, "Subjective judgment"),
    ]


@pytest.fixture
def sample_verifications():
    """
    Sample FactVerification objects with all verdict types
    """
    from src.trust.fact_verifier import Claim, FactVerification

    return [
        FactVerification(
            claim=Claim("Python was created in 1991", "FACT", 0.9, "Historical fact"),
            verdict="VERIFIED",
            confidence=0.95,
            reasoning="Confirmed by multiple authoritative sources",
            caveats=["First public release was February 1991"],
            contradictions=[],
        ),
        FactVerification(
            claim=Claim(
                "The sky appears blue due to Rayleigh scattering", "FACT", 0.9, "Scientific fact"
            ),
            verdict="VERIFIED",
            confidence=0.98,
            reasoning="Well-established scientific phenomenon",
            caveats=[],
            contradictions=[],
        ),
        FactVerification(
            claim=Claim("The president is John Smith", "FACT", 0.8, "Time-sensitive claim"),
            verdict="CONTRADICTED",
            confidence=0.9,
            reasoning="This contradicts current factual information",
            caveats=[],
            contradictions=["The current president is not John Smith"],
        ),
        FactVerification(
            claim=Claim(
                "The quantum flux capacitor was invented in 1985", "FACT", 0.7, "Unverifiable claim"
            ),
            verdict="UNVERIFIABLE",
            confidence=0.0,
            reasoning="Cannot verify this claim with available sources; appears to be fictional",
            caveats=[],
            contradictions=[],
        ),
        FactVerification(
            claim=Claim("The CEO is Jane Doe", "FACT", 0.8, "Time-sensitive corporate claim"),
            verdict="OUTDATED",
            confidence=0.85,
            reasoning="This claim was true in 2023 but is now outdated",
            caveats=[],
            contradictions=[],
            temporal_check={
                "still_current": False,
                "confidence": 0.9,
                "reasoning": "The CEO changed in 2024",
                "checked_date": "2026-01-01",
                "source": "Company Leadership Page",
                "update_info": "Current CEO is John Brown as of January 2024",
            },
        ),
        FactVerification(
            claim=Claim("AI might transform industries", "SPECULATION", 0.5, "Future prediction"),
            verdict="UNVERIFIABLE",
            confidence=1.0,
            reasoning="Claim is speculation and cannot be factually verified",
            caveats=[],
            contradictions=[],
        ),
    ]


@pytest.fixture
def sample_fact_analysis():
    """
    Complete fact analysis dictionary with all verdict types
    """
    return {
        "verifications": [
            {
                "claim": {
                    "text": "Python was created in 1991",
                    "type": "FACT",
                    "confidence": 0.9,
                    "reasoning": "Historical fact",
                },
                "verdict": "VERIFIED",
                "confidence": 0.95,
                "reasoning": "Confirmed by multiple authoritative sources",
                "caveats": ["First public release was February 1991"],
                "contradictions": [],
            },
            {
                "claim": {
                    "text": "The quantum flux capacitor was invented in 1985",
                    "type": "FACT",
                    "confidence": 0.7,
                    "reasoning": "Unverifiable claim",
                },
                "verdict": "UNVERIFIABLE",
                "confidence": 0.0,
                "reasoning": "Cannot verify this claim with available sources; appears to be fictional",
                "caveats": [],
                "contradictions": [],
            },
            {
                "claim": {
                    "text": "The president is John Smith",
                    "type": "FACT",
                    "confidence": 0.8,
                    "reasoning": "Time-sensitive claim",
                },
                "verdict": "CONTRADICTED",
                "confidence": 0.9,
                "reasoning": "This contradicts current factual information",
                "caveats": [],
                "contradictions": ["The current president is not John Smith"],
            },
            {
                "claim": {
                    "text": "The CEO is Jane Doe",
                    "type": "FACT",
                    "confidence": 0.8,
                    "reasoning": "Time-sensitive claim",
                },
                "verdict": "OUTDATED",
                "confidence": 0.85,
                "reasoning": "This claim was true in 2023 but is now outdated",
                "caveats": [],
                "contradictions": [],
                "temporal_check": {
                    "still_current": False,
                    "confidence": 0.9,
                    "reasoning": "The CEO changed in 2024",
                    "checked_date": "2026-01-01",
                    "source": "Company Leadership Page",
                    "update_info": "Current CEO is John Brown as of January 2024",
                },
            },
        ],
        "total_claims": 4,
        "verified_count": 1,
        "uncertain_count": 1,
        "contradicted_count": 1,
        "error_count": 0,
    }


@pytest.fixture
def sample_bias_analysis():
    """
    Sample BiasAnalysis dictionary for testing
    """
    return {
        "framing_issues": [
            {
                "frame_type": "crisis-urgency",
                "text": "The situation demands immediate action",
                "effect": "Creates artificial urgency without justification",
                "alternative": "The situation requires consideration and appropriate response",
            }
        ],
        "assumptions": [
            {
                "assumption": "All users prioritize speed over accessibility",
                "basis": "Focus on performance optimization without mentioning accessibility",
                "impact": "Excludes users with disabilities from consideration",
            }
        ],
        "omissions": [
            {
                "missing_perspective": "Environmental impact of the solution",
                "relevance": "Critical for sustainability assessment",
                "suggestion": "Include carbon footprint and environmental considerations",
            }
        ],
        "loaded_terms": [
            {
                "term": "radical changes",
                "connotation": "Extreme, potentially dangerous",
                "neutral_alternative": "significant changes",
            }
        ],
    }


@pytest.fixture
def sample_intimacy_analysis():
    """
    Sample IntimacyAnalysis dictionary for testing
    """
    return {
        "issues": [
            {
                "category": "EMOTION",
                "text": "I'm excited to help you",
                "explanation": "AI cannot experience emotions like excitement",
                "severity": "HIGH",
                "professional_alternative": "I'm ready to assist you",
            },
            {
                "category": "FALSE_EMPATHY",
                "text": "I understand how frustrating this must be",
                "explanation": "AI cannot genuinely understand human emotions",
                "severity": "MEDIUM",
                "professional_alternative": "I recognize this situation may be challenging",
            },
        ],
        "overall_tone": "FAMILIAR",
        "summary": "Response contains emotion claims and false empathy",
        "total_issues": 2,
        "high_severity_count": 1,
        "medium_severity_count": 1,
        "low_severity_count": 0,
    }


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
