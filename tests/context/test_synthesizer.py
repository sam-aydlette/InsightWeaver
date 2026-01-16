"""
Tests for Narrative Synthesizer
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.context.synthesizer import NarrativeSynthesizer


class TestNarrativeSynthesizerInit:
    """Tests for NarrativeSynthesizer initialization"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_init_creates_components(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should create curator, client, and reflection engine"""
        NarrativeSynthesizer()

        mock_curator.assert_called_once()
        mock_client.assert_called_once()
        mock_reflection.assert_called_once()

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_init_with_topic_filters(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should pass topic filters to curator"""
        filters = {"topics": ["cybersecurity"]}

        NarrativeSynthesizer(topic_filters=filters)

        mock_curator.assert_called_with(topic_filters=filters)


class TestBuildSynthesisTask:
    """Tests for synthesis task building"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_build_synthesis_task_includes_article_count(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should include article count in task prompt"""
        synthesizer = NarrativeSynthesizer()

        task = synthesizer._build_synthesis_task(25)

        assert "25" in task
        assert "articles" in task.lower()

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_build_synthesis_task_includes_json_structure(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should include expected JSON structure"""
        synthesizer = NarrativeSynthesizer()

        task = synthesizer._build_synthesis_task(10)

        assert "bottom_line" in task
        assert "trends_and_patterns" in task
        assert "priority_events" in task
        assert "predictions_scenarios" in task


class TestBuildSynthesisTaskWithCitations:
    """Tests for citation-enhanced synthesis task"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_build_task_with_citations_includes_article_refs(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should include article reference list"""
        synthesizer = NarrativeSynthesizer()
        articles = [
            {"id": 1, "title": "Article 1", "source": "Source 1", "published_date": "2024-01-15"},
            {"id": 2, "title": "Article 2", "source": "Source 2", "published_date": "2024-01-15"},
        ]

        task, citation_map = synthesizer._build_synthesis_task_with_citations(articles, 2)

        assert "[1]" in task
        assert "[2]" in task
        assert "Article 1" in task
        assert "Article 2" in task
        # Verify citation_map is also returned
        assert "1" in citation_map
        assert "2" in citation_map
        assert citation_map["1"]["title"] == "Article 1"

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_build_task_with_citations_includes_citation_instructions(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should include citation instructions"""
        synthesizer = NarrativeSynthesizer()
        articles = [{"id": 1, "title": "Test", "source": "Test", "published_date": "2024-01-15"}]

        task, citation_map = synthesizer._build_synthesis_task_with_citations(articles, 1)

        assert "CRITICAL" in task
        assert "citation" in task.lower()
        assert "article_citations" in task


class TestParseSynthesisResponse:
    """Tests for parsing Claude's response"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_parse_valid_json(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should parse valid JSON response"""
        synthesizer = NarrativeSynthesizer()
        response = json.dumps({
            "bottom_line": {"summary": "Test summary"},
            "trends_and_patterns": {},
            "priority_events": [],
            "predictions_scenarios": {},
        })

        result = synthesizer._parse_synthesis_response(response)

        assert result["bottom_line"]["summary"] == "Test summary"

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_parse_removes_markdown_blocks(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should remove markdown code blocks"""
        synthesizer = NarrativeSynthesizer()
        response = """```json
        {"bottom_line": {"summary": "Test"}, "trends_and_patterns": {}, "priority_events": [], "predictions_scenarios": {}}
        ```"""

        result = synthesizer._parse_synthesis_response(response)

        assert result["bottom_line"]["summary"] == "Test"

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_parse_adds_timestamp(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should add timestamp to metadata"""
        synthesizer = NarrativeSynthesizer()
        response = json.dumps({
            "bottom_line": {},
            "trends_and_patterns": {},
            "priority_events": [],
            "predictions_scenarios": {},
        })

        result = synthesizer._parse_synthesis_response(response)

        assert "metadata" in result
        assert "generated_at" in result["metadata"]

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_parse_invalid_json_returns_fallback(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should return fallback structure for invalid JSON"""
        synthesizer = NarrativeSynthesizer()
        response = "This is not valid JSON"

        result = synthesizer._parse_synthesis_response(response)

        assert "bottom_line" in result
        assert "trends_and_patterns" in result
        assert "parse_error" in result["metadata"]


class TestExtractNarrativeForVerification:
    """Tests for extracting narrative text"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_extract_includes_bottom_line(
        self, mock_reflection, mock_client, mock_curator, sample_synthesis_data
    ):
        """Should include bottom line summary"""
        synthesizer = NarrativeSynthesizer()

        result = synthesizer._extract_narrative_for_verification(sample_synthesis_data)

        assert "Test summary" in result

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_extract_includes_trends(
        self, mock_reflection, mock_client, mock_curator, sample_synthesis_data
    ):
        """Should include trend information"""
        synthesizer = NarrativeSynthesizer()

        result = synthesizer._extract_narrative_for_verification(sample_synthesis_data)

        assert "cybersecurity" in result.lower()

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_extract_includes_events(
        self, mock_reflection, mock_client, mock_curator, sample_synthesis_data
    ):
        """Should include priority events"""
        synthesizer = NarrativeSynthesizer()

        result = synthesizer._extract_narrative_for_verification(sample_synthesis_data)

        assert "council meeting" in result.lower()

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_extract_handles_string_events(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should handle events that are strings (Claude formatting issue)"""
        synthesizer = NarrativeSynthesizer()
        data = {
            "bottom_line": {"summary": "Summary"},
            "trends_and_patterns": {},
            "priority_events": ["Event as string", {"event": "Event as dict"}],
            "predictions_scenarios": {},
        }

        result = synthesizer._extract_narrative_for_verification(data)

        assert "Event as string" in result
        assert "Event as dict" in result


class TestEvaluateTrustThreshold:
    """Tests for trust threshold evaluation"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_passes_with_good_scores(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should pass with good trust scores"""
        synthesizer = NarrativeSynthesizer()
        analysis = {
            "facts": {"contradicted_count": 0, "total_claims": 20},
            "bias": {"loaded_language": []},
            "intimacy": {"issues": []},
        }

        result = synthesizer._evaluate_trust_threshold(analysis)

        assert result is True

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_fails_with_too_many_contradictions(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should fail when >5% contradictions"""
        synthesizer = NarrativeSynthesizer()
        analysis = {
            "facts": {"contradicted_count": 2, "total_claims": 10},  # 20% contradicted
            "bias": {"loaded_language": []},
            "intimacy": {"issues": []},
        }

        result = synthesizer._evaluate_trust_threshold(analysis)

        assert result is False

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_fails_with_too_much_bias(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should fail when >3 loaded language instances"""
        synthesizer = NarrativeSynthesizer()
        analysis = {
            "facts": {"contradicted_count": 0, "total_claims": 10},
            "bias": {"loaded_language": ["word1", "word2", "word3", "word4"]},
            "intimacy": {"issues": []},
        }

        result = synthesizer._evaluate_trust_threshold(analysis)

        assert result is False

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_fails_with_high_intimacy_issues(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should fail with high-severity intimacy issues"""
        synthesizer = NarrativeSynthesizer()
        analysis = {
            "facts": {"contradicted_count": 0, "total_claims": 10},
            "bias": {"loaded_language": []},
            "intimacy": {"issues": [{"severity": "HIGH", "text": "issue"}]},
        }

        result = synthesizer._evaluate_trust_threshold(analysis)

        assert result is False

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_passes_with_medium_intimacy_issues(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should pass with medium-severity intimacy issues"""
        synthesizer = NarrativeSynthesizer()
        analysis = {
            "facts": {"contradicted_count": 0, "total_claims": 10},
            "bias": {"loaded_language": []},
            "intimacy": {"issues": [{"severity": "MEDIUM", "text": "issue"}]},
        }

        result = synthesizer._evaluate_trust_threshold(analysis)

        assert result is True


class TestAddTrustConstraints:
    """Tests for adding trust constraints to failed attempts"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_adds_fact_constraints(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should add fact accuracy constraints for fact failures"""
        synthesizer = NarrativeSynthesizer()
        task = "Original task"
        history = [
            {"analysis": {"facts": {"contradicted_count": 2}}}
        ]

        result = synthesizer._add_trust_constraints(task, history)

        assert "FACTUAL ACCURACY" in result
        assert "ONLY make claims" in result

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_adds_bias_constraints(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should add bias constraints for bias failures"""
        synthesizer = NarrativeSynthesizer()
        task = "Original task"
        history = [
            {"analysis": {"bias": {"loaded_language": ["a", "b", "c", "d"]}}}
        ]

        result = synthesizer._add_trust_constraints(task, history)

        assert "NEUTRAL FRAMING" in result
        assert "neutral" in result.lower()

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_adds_tone_constraints(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should add tone constraints for intimacy failures"""
        synthesizer = NarrativeSynthesizer()
        task = "Original task"
        history = [
            {"analysis": {"intimacy": {"issues": [{"severity": "HIGH"}]}}}
        ]

        result = synthesizer._add_trust_constraints(task, history)

        assert "PROFESSIONAL TONE" in result


class TestEstimateTokens:
    """Tests for token estimation"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_estimate_tokens_basic(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should estimate tokens from context"""
        synthesizer = NarrativeSynthesizer()
        context = {"articles": [{"content": "a" * 100}], "memory": "b" * 100}

        result = synthesizer._estimate_tokens(context)

        assert result > 0

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_estimate_tokens_empty_context(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should handle empty context"""
        synthesizer = NarrativeSynthesizer()

        result = synthesizer._estimate_tokens({})

        assert result >= 0


class TestHashProfile:
    """Tests for profile hashing"""

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_hash_profile_consistent(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should produce consistent hash for same profile"""
        synthesizer = NarrativeSynthesizer()
        profile = {"location": "Fairfax", "domains": ["cyber"]}

        hash1 = synthesizer._hash_profile(profile)
        hash2 = synthesizer._hash_profile(profile)

        assert hash1 == hash2

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_hash_profile_different_for_different_profiles(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should produce different hash for different profiles"""
        synthesizer = NarrativeSynthesizer()

        hash1 = synthesizer._hash_profile({"location": "Fairfax"})
        hash2 = synthesizer._hash_profile({"location": "Arlington"})

        assert hash1 != hash2

    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    def test_hash_profile_none_returns_none(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should return 'none' for None profile"""
        synthesizer = NarrativeSynthesizer()

        result = synthesizer._hash_profile(None)

        assert result == "none"


class TestSynthesize:
    """Tests for main synthesize method"""

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    async def test_synthesize_no_articles(
        self, mock_reflection, mock_client, mock_curator
    ):
        """Should return no_articles status when no articles available"""
        mock_curator_instance = MagicMock()
        mock_curator.return_value = mock_curator_instance
        mock_curator_instance.curate_for_narrative_synthesis = AsyncMock(
            return_value={"articles": []}
        )

        synthesizer = NarrativeSynthesizer()

        result = await synthesizer.synthesize()

        assert result["status"] == "no_articles"
        assert result["articles_analyzed"] == 0


class TestSynthesizeWithTrustVerificationCitationMap:
    """Integration tests for citation_map handling in trust-verified synthesis"""

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    @patch("src.context.synthesizer.TrustPipeline", create=True)
    async def test_citation_map_injected_from_articles(
        self, mock_trust_pipeline_class, mock_reflection, mock_client, mock_curator
    ):
        """Citation map should be built from articles and injected into synthesis output"""
        # Setup curator to return test articles
        test_articles = [
            {
                "id": 1,
                "title": "Article One",
                "source": "Source A",
                "url": "https://example.com/1",
                "published_date": "2025-01-15",
            },
            {
                "id": 2,
                "title": "Article Two",
                "source": "Source B",
                "url": "https://example.com/2",
                "published_date": "2025-01-16",
            },
        ]
        mock_curator_instance = MagicMock()
        mock_curator.return_value = mock_curator_instance
        mock_curator_instance.curate_for_narrative_synthesis = AsyncMock(
            return_value={"articles": test_articles}
        )

        # Setup Claude to return valid synthesis (without citation_map - simulating real behavior)
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.analyze_with_context = AsyncMock(
            return_value=json.dumps({
                "bottom_line": {"summary": "Test summary^[1,2]", "article_citations": [1, 2]},
                "trends_and_patterns": {"local": [], "national": []},
                "priority_events": [],
                "predictions_scenarios": {},
                "metadata": {
                    "articles_analyzed": 2,
                    "generated_at": "2025-01-15T00:00:00",
                    # Note: No citation_map - Claude didn't return it
                },
            })
        )

        # Setup trust pipeline to pass verification
        mock_trust_pipeline_instance = MagicMock()
        mock_trust_pipeline_class.return_value = mock_trust_pipeline_instance
        mock_trust_pipeline_instance.analyze_response = AsyncMock(
            return_value={
                "facts": {"contradicted_count": 0, "total_claims": 5},
                "bias": {"loaded_language": []},
                "intimacy": {"issues": []},
            }
        )

        # Patch the import inside the method
        with patch("src.context.synthesizer.TrustPipeline", mock_trust_pipeline_class):
            synthesizer = NarrativeSynthesizer()
            result = await synthesizer.synthesize_with_trust_verification(
                hours=24, max_articles=10, max_retries=1
            )

        # Verify synthesis succeeded
        assert result["status"] == "success"
        assert "synthesis_data" in result

        # KEY TEST: Citation map should be present and match our articles
        synthesis_data = result["synthesis_data"]
        assert "metadata" in synthesis_data
        assert "citation_map" in synthesis_data["metadata"]

        citation_map = synthesis_data["metadata"]["citation_map"]
        assert "1" in citation_map
        assert "2" in citation_map
        assert citation_map["1"]["title"] == "Article One"
        assert citation_map["1"]["source"] == "Source A"
        assert citation_map["1"]["url"] == "https://example.com/1"
        assert citation_map["2"]["title"] == "Article Two"
        assert citation_map["2"]["source"] == "Source B"

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    @patch("src.context.synthesizer.ReflectionEngine")
    @patch("src.context.synthesizer.TrustPipeline", create=True)
    async def test_citation_map_overrides_claude_response(
        self, mock_trust_pipeline_class, mock_reflection, mock_client, mock_curator
    ):
        """Our citation map should override any citation_map Claude returns"""
        # Setup curator with specific articles
        test_articles = [
            {
                "id": 99,
                "title": "Correct Title",
                "source": "Correct Source",
                "url": "https://correct.com",
                "published_date": "2025-01-15",
            },
        ]
        mock_curator_instance = MagicMock()
        mock_curator.return_value = mock_curator_instance
        mock_curator_instance.curate_for_narrative_synthesis = AsyncMock(
            return_value={"articles": test_articles}
        )

        # Claude returns a WRONG citation_map (simulating the bug we're fixing)
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.analyze_with_context = AsyncMock(
            return_value=json.dumps({
                "bottom_line": {"summary": "Test^[1]", "article_citations": [1]},
                "trends_and_patterns": {},
                "priority_events": [],
                "predictions_scenarios": {},
                "metadata": {
                    "articles_analyzed": 1,
                    "citation_map": {
                        "1": {
                            "article_id": 999,
                            "title": "WRONG Title",
                            "source": "WRONG Source",
                            "url": "https://wrong.com",
                        }
                    },
                },
            })
        )

        # Setup trust pipeline
        mock_trust_pipeline_instance = MagicMock()
        mock_trust_pipeline_class.return_value = mock_trust_pipeline_instance
        mock_trust_pipeline_instance.analyze_response = AsyncMock(
            return_value={
                "facts": {"contradicted_count": 0, "total_claims": 1},
                "bias": {"loaded_language": []},
                "intimacy": {"issues": []},
            }
        )

        with patch("src.context.synthesizer.TrustPipeline", mock_trust_pipeline_class):
            synthesizer = NarrativeSynthesizer()
            result = await synthesizer.synthesize_with_trust_verification(
                hours=24, max_articles=10, max_retries=1
            )

        # KEY TEST: Our citation_map should override Claude's wrong one
        citation_map = result["synthesis_data"]["metadata"]["citation_map"]
        assert citation_map["1"]["title"] == "Correct Title"  # Not "WRONG Title"
        assert citation_map["1"]["source"] == "Correct Source"  # Not "WRONG Source"
        assert citation_map["1"]["url"] == "https://correct.com"  # Not "https://wrong.com"
