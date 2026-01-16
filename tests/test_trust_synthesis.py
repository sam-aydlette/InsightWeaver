"""
Unit tests for trust-integrated synthesis with citations
"""

import json
from datetime import datetime

import pytest

from src.context.synthesizer import NarrativeSynthesizer


class TestCitationPromptGeneration:
    """Test citation-enhanced prompt generation"""

    def test_build_synthesis_task_with_citations_basic(self):
        """Test basic citation prompt generation with sample articles"""
        synthesizer = NarrativeSynthesizer()

        # Sample articles
        articles = [
            {
                "id": 1,
                "title": "Cybersecurity Spending Increases",
                "source": "TechNews",
                "url": "https://example.com/article1",
                "published_date": "2025-01-15",
            },
            {
                "id": 2,
                "title": "Local Council Votes on Zoning",
                "source": "LocalNews",
                "url": "https://example.com/article2",
                "published_date": "2025-01-16",
            },
        ]

        # Generate citation prompt
        prompt = synthesizer._build_synthesis_task_with_citations(articles, len(articles))

        # Verify prompt contains citation instructions
        assert "CRITICAL REQUIREMENT: Citation Discipline" in prompt
        assert "claim^[1,3]" in prompt
        assert "article_citations" in prompt

        # Verify article reference list is included
        assert "[1] Cybersecurity Spending Increases - TechNews" in prompt
        assert "[2] Local Council Votes on Zoning - LocalNews" in prompt

        # Verify citation map structure is in prompt
        assert "citation_map" in prompt
        assert "article_id" in prompt

    def test_citation_map_json_escaping(self):
        """Test that citation map properly escapes special characters"""
        synthesizer = NarrativeSynthesizer()

        # Articles with special characters that need escaping
        articles = [
            {
                "id": 1,
                "title": 'Article with "quotes" and special chars',
                "source": "News & Analysis",
                "url": "https://example.com/article?id=1&test=true",
                "published_date": "2025-01-15",
            }
        ]

        prompt = synthesizer._build_synthesis_task_with_citations(articles, len(articles))

        # Extract the citation_map section from the prompt
        # The prompt should contain properly escaped JSON
        assert "citation_map" in prompt
        # Verify the special characters are handled (quotes should be escaped in JSON)
        assert "News & Analysis" in prompt or "News \\u0026 Analysis" in prompt

    def test_citation_prompt_includes_examples(self):
        """Test that citation prompt includes clear examples"""
        synthesizer = NarrativeSynthesizer()

        articles = [
            {
                "id": 1,
                "title": "Test Article",
                "source": "Test Source",
                "url": "https://test.com",
                "published_date": "2025-01-15",
            }
        ]

        prompt = synthesizer._build_synthesis_task_with_citations(articles, len(articles))

        # Verify citation examples are present
        assert "Federal cybersecurity spending increased 15%^[1,3]" in prompt
        assert "Local tech hiring^[1]" in prompt
        assert "23% year-over-year^[1,4]" in prompt

        # Verify citation rules are clear
        assert "ALWAYS cite: Quantitative claims" in prompt
        assert "ALWAYS cite: Specific events with dates/times" in prompt
        assert "DO NOT cite: Your own analytical conclusions" in prompt

    def test_empty_articles_list(self):
        """Test prompt generation with empty articles list"""
        synthesizer = NarrativeSynthesizer()

        articles = []

        prompt = synthesizer._build_synthesis_task_with_citations(articles, 0)

        # Should still generate valid prompt structure
        assert "CRITICAL REQUIREMENT: Citation Discipline" in prompt
        assert "Article Reference List" in prompt
        assert "citation_map" in prompt

    def test_missing_optional_fields(self):
        """Test prompt generation when articles have missing optional fields"""
        synthesizer = NarrativeSynthesizer()

        # Articles with minimal fields
        articles = [
            {"id": 1},  # Missing title, source, url, published_date
            {"id": 2, "title": "Test"},  # Missing other fields
        ]

        prompt = synthesizer._build_synthesis_task_with_citations(articles, len(articles))

        # Should use default values
        assert "[1] Untitled - Unknown" in prompt
        assert "[2] Test - Unknown" in prompt
        assert "No date" in prompt


class TestCitationParsing:
    """Test parsing of synthesis responses with citations"""

    def test_parse_synthesis_with_citations(self):
        """Test parsing synthesis response that includes citations"""
        synthesizer = NarrativeSynthesizer()

        # Sample response with citations
        response = json.dumps(
            {
                "bottom_line": {
                    "summary": "Cybersecurity spending increased 15%^[1] due to new mandates^[2]",
                    "immediate_actions": ["Review security budget^[1]"],
                    "article_citations": [1, 2],
                },
                "trends_and_patterns": {
                    "local": [
                        {
                            "subject": "Tech hiring^[1]",
                            "direction": "increasing",
                            "quantifier": "23% year-over-year^[1]",
                            "description": "Driven by AI startups^[1]",
                            "confidence": 0.85,
                            "article_citations": [1],
                        }
                    ],
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
                    "articles_analyzed": 2,
                    "generated_at": datetime.utcnow().isoformat(),
                    "citation_map": {
                        "1": {
                            "article_id": 1,
                            "title": "Tech News",
                            "source": "TechSource",
                            "url": "https://test.com",
                        },
                        "2": {
                            "article_id": 2,
                            "title": "Security Update",
                            "source": "SecSource",
                            "url": "https://test2.com",
                        },
                    },
                },
            }
        )

        parsed = synthesizer._parse_synthesis_response(response)

        # Verify citation fields are preserved
        assert "article_citations" in parsed["bottom_line"]
        assert parsed["bottom_line"]["article_citations"] == [1, 2]
        assert "article_citations" in parsed["trends_and_patterns"]["local"][0]
        assert "citation_map" in parsed["metadata"]
        assert "1" in parsed["metadata"]["citation_map"]

    def test_parse_synthesis_without_citations_backward_compat(self):
        """Test parsing old synthesis format without citations (backward compatibility)"""
        synthesizer = NarrativeSynthesizer()

        # Old format without citation fields
        response = json.dumps(
            {
                "bottom_line": {
                    "summary": "Cybersecurity spending increased 15%",
                    "immediate_actions": [],
                },
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
                "metadata": {"articles_analyzed": 2, "generated_at": datetime.utcnow().isoformat()},
            }
        )

        parsed = synthesizer._parse_synthesis_response(response)

        # Should parse successfully even without citation fields
        assert parsed is not None
        assert "bottom_line" in parsed
        assert "metadata" in parsed
        # Citation fields are optional - old format should still work

    def test_parse_synthesis_fallback_includes_citations(self):
        """Test that fallback structure includes empty citation fields"""
        synthesizer = NarrativeSynthesizer()

        # Invalid JSON to trigger fallback
        response = "This is not valid JSON"

        parsed = synthesizer._parse_synthesis_response(response)

        # Fallback structure should include citation fields
        assert "article_citations" in parsed["bottom_line"]
        assert parsed["bottom_line"]["article_citations"] == []
        assert "citation_map" in parsed["metadata"]
        assert parsed["metadata"]["citation_map"] == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
