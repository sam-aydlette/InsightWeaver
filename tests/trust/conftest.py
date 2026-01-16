"""
Trust module specific test fixtures
Provides component instances and trust-specific test data
"""

import json

import pytest


@pytest.fixture
def mock_yaml_sources():
    """
    Mock YAML sources config for source matcher tests
    Includes Wikipedia current leaders source for testing
    """
    return {
        "sources": [
            {
                "name": "Wikipedia - Current Leaders",
                "keywords": ["president", "prime minister", "leader", "current"],
                "url": "https://en.wikipedia.org/wiki/List_of_current_heads_of_state_and_government",
                "query_prompt": "Find current leader information from Wikipedia list",
                "requires_country_extraction": False,
            },
            {
                "name": "Test Economic Source",
                "keywords": ["economy", "gdp", "economic"],
                "url": "https://test.worldbank.org/data",
                "query_prompt": "Find economic data",
            },
        ],
        "fallback": {"enabled": True, "search_engine": "brave", "max_results": 3},
    }


@pytest.fixture
def fact_verifier(mock_claude_client):
    """
    FactVerifier instance with mocked ClaudeClient
    """
    from src.trust.fact_verifier import FactVerifier

    return FactVerifier(mock_claude_client)


@pytest.fixture
def bias_analyzer(mock_claude_client):
    """
    BiasAnalyzer instance with mocked ClaudeClient
    """
    from src.trust.bias_analyzer import BiasAnalyzer

    return BiasAnalyzer(mock_claude_client)


@pytest.fixture
def intimacy_detector(mock_claude_client):
    """
    IntimacyDetector instance with mocked ClaudeClient
    """
    from src.trust.intimacy_detector import IntimacyDetector

    return IntimacyDetector(mock_claude_client)


@pytest.fixture
def source_matcher(mock_claude_client, mock_authoritative_sources, mocker):
    """
    AuthoritativeSourceMatcher with mocked dependencies
    """

    from src.trust.source_matcher import AuthoritativeSourceMatcher

    # Mock the Path and yaml loading to return our test sources
    mock_path = mocker.patch("src.trust.source_matcher.Path")
    mock_yaml_load = mocker.patch("src.trust.source_matcher.yaml.safe_load")

    # Configure mocks
    mock_path.return_value.__truediv__.return_value = mocker.MagicMock()
    mock_yaml_load.return_value = mock_authoritative_sources

    # Create instance
    matcher = AuthoritativeSourceMatcher(claude_client=mock_claude_client)
    matcher.sources = mock_authoritative_sources["sources"]
    matcher.fallback_config = mock_authoritative_sources["fallback"]

    return matcher


@pytest.fixture
def trust_pipeline(mock_claude_client, mocker):
    """
    TrustPipeline instance with mocked dependencies
    """
    from src.trust.trust_pipeline import TrustPipeline

    # Create instance without initialization (we'll inject mocks)
    pipeline = TrustPipeline.__new__(TrustPipeline)
    pipeline.client = mock_claude_client

    # Create mocked sub-components
    pipeline.fact_verifier = mocker.MagicMock()
    pipeline.fact_verifier.verify = mocker.AsyncMock(return_value=[])

    pipeline.bias_analyzer = mocker.MagicMock()
    from src.trust.bias_analyzer import BiasAnalysis

    pipeline.bias_analyzer.analyze = mocker.AsyncMock(return_value=BiasAnalysis([], [], [], []))

    pipeline.intimacy_detector = mocker.MagicMock()
    from src.trust.intimacy_detector import IntimacyAnalysis

    pipeline.intimacy_detector.detect = mocker.AsyncMock(
        return_value=IntimacyAnalysis([], "PROFESSIONAL", "No issues")
    )

    pipeline.source_matcher = mocker.MagicMock()
    pipeline.source_matcher.find_source = mocker.AsyncMock(return_value=None)

    return pipeline


@pytest.fixture
def complete_analysis_result():
    """
    Complete analysis result with all components analyzed
    """
    return {
        "analyzed": True,
        "response_length": 250,
        "facts": {
            "analyzed": True,
            "verifications": [
                {
                    "claim": {
                        "text": "Fact 1",
                        "type": "FACT",
                        "confidence": 0.9,
                        "reasoning": "Test",
                    },
                    "verdict": "VERIFIED",
                    "confidence": 0.95,
                    "reasoning": "Confirmed",
                    "caveats": [],
                    "contradictions": [],
                },
                {
                    "claim": {
                        "text": "Fact 2",
                        "type": "FACT",
                        "confidence": 0.8,
                        "reasoning": "Test",
                    },
                    "verdict": "UNVERIFIABLE",
                    "confidence": 0.0,
                    "reasoning": "Cannot verify with available sources",
                    "caveats": [],
                    "contradictions": [],
                },
            ],
            "total_claims": 2,
            "verified_count": 1,
            "uncertain_count": 1,
            "contradicted_count": 0,
            "error_count": 0,
        },
        "bias": {
            "framing_issues": [],
            "assumptions": [],
            "omissions": [],
            "loaded_terms": [],
            "total_issues": 0,
            "analyzed": True,
        },
        "intimacy": {
            "issues": [],
            "overall_tone": "PROFESSIONAL",
            "summary": "No intimacy issues detected",
            "total_issues": 0,
            "high_severity_count": 0,
            "medium_severity_count": 0,
            "low_severity_count": 0,
            "analyzed": True,
        },
    }


@pytest.fixture
def json_claim_extraction_response():
    """
    Sample JSON response for claim extraction from Claude
    """
    return json.dumps(
        {
            "claims": [
                {
                    "text": "Python was created by Guido van Rossum",
                    "type": "FACT",
                    "confidence": 0.95,
                    "reasoning": "Historical fact with clear attribution",
                },
                {
                    "text": "Python is the best programming language",
                    "type": "OPINION",
                    "confidence": 0.5,
                    "reasoning": "Subjective judgment without objective criteria",
                },
                {
                    "text": "Python might become more popular",
                    "type": "SPECULATION",
                    "confidence": 0.4,
                    "reasoning": "Future prediction without supporting evidence",
                },
            ]
        }
    )


@pytest.fixture
def json_fact_verification_response():
    """
    Sample JSON response for fact verification from Claude
    """
    return json.dumps(
        {
            "verdict": "VERIFIED",
            "confidence": 0.92,
            "reasoning": "This claim is well-supported by historical records and documentation",
            "caveats": ["First public release was in February 1991"],
            "contradictions": [],
        }
    )


@pytest.fixture
def json_bias_analysis_response():
    """
    Sample JSON response for bias analysis from Claude
    """
    return json.dumps(
        {
            "framing": [
                {
                    "frame_type": "problem-solution",
                    "text": "The crisis demands action",
                    "effect": "Creates urgency",
                    "alternative": "The situation requires attention",
                }
            ],
            "assumptions": [
                {
                    "assumption": "Users want speed",
                    "basis": "Focus on performance",
                    "impact": "Ignores accessibility",
                }
            ],
            "omissions": [
                {
                    "missing_perspective": "Environmental impact",
                    "relevance": "Critical for sustainability",
                    "suggestion": "Include carbon footprint",
                }
            ],
            "loaded_language": [
                {"term": "radical", "connotation": "Extreme", "neutral_alternative": "significant"}
            ],
        }
    )


@pytest.fixture
def json_intimacy_detection_response():
    """
    Sample JSON response for intimacy detection from Claude
    """
    return json.dumps(
        {
            "issues": [
                {
                    "category": "EMOTION",
                    "text": "I'm excited to help",
                    "explanation": "AI cannot experience emotions",
                    "severity": "HIGH",
                    "professional_alternative": "I'm ready to assist",
                }
            ],
            "overall_tone": "FAMILIAR",
            "summary": "Contains emotion claims",
        }
    )


@pytest.fixture
def json_source_matching_response():
    """
    Sample JSON response for source matching from Claude
    """
    return json.dumps(
        {
            "best_match_id": 0,
            "confidence": 0.95,
            "reasoning": "Query asks about US President, matches first source perfectly",
        }
    )


@pytest.fixture
def json_time_sensitivity_response():
    """
    Sample JSON response for time sensitivity analysis from Claude
    """
    return json.dumps(
        {
            "is_time_sensitive": True,
            "facts_needed": ["current president"],
            "source_type": "government_leadership",
            "reasoning": "Query asks about current political leadership",
        }
    )


@pytest.fixture
def json_country_extraction_response():
    """
    Sample JSON response for country extraction from Claude
    """
    return json.dumps(
        {"country": "India", "confidence": 0.98, "reasoning": "Query explicitly mentions India"}
    )
