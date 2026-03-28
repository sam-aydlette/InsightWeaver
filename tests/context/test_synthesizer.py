"""
Tests for Two-Pass Narrative Synthesizer
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.context.synthesizer import NarrativeSynthesizer


class TestSynthesizerConfiguration:
    """Tests for synthesizer configuration behavior"""

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_topic_filters_are_applied_to_curation(self, mock_client, mock_curator, mock_frame_mgr):
        """Topic filters should affect which articles are included in synthesis"""
        filters = {"topics": ["cybersecurity"]}

        NarrativeSynthesizer(topic_filters=filters)

        mock_curator.assert_called_with(topic_filters=filters)


class TestJsonParsing:
    """Tests for Claude JSON response parsing"""

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_parses_valid_json(self, mock_client, mock_curator, mock_frame_mgr):
        """Valid JSON should be parsed correctly"""
        synthesizer = NarrativeSynthesizer()
        response = json.dumps({"clusters": [{"title": "Test", "article_ids": [1]}]})

        result = synthesizer._parse_json_response(response)

        assert result["clusters"][0]["title"] == "Test"

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_strips_markdown_fences(self, mock_client, mock_curator, mock_frame_mgr):
        """Should handle JSON wrapped in markdown code blocks"""
        synthesizer = NarrativeSynthesizer()
        response = '```json\n{"key": "value"}\n```'

        result = synthesizer._parse_json_response(response)

        assert result["key"] == "value"

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_returns_empty_dict_on_invalid_json(self, mock_client, mock_curator, mock_frame_mgr):
        """Invalid JSON should return empty dict, not crash"""
        synthesizer = NarrativeSynthesizer()

        result = synthesizer._parse_json_response("This is not JSON")

        assert result == {}


class TestCitationMap:
    """Tests for citation map building"""

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_builds_citation_map_from_articles(self, mock_client, mock_curator, mock_frame_mgr):
        """Citation map should index articles by 1-based position"""
        synthesizer = NarrativeSynthesizer()
        articles = [
            {"id": 10, "title": "Article A", "source": "Source A", "url": "https://a.com"},
            {"id": 20, "title": "Article B", "source": "Source B", "url": "https://b.com"},
        ]

        result = synthesizer._build_citation_map(articles)

        assert result["1"]["title"] == "Article A"
        assert result["1"]["article_id"] == 10
        assert result["2"]["title"] == "Article B"
        assert result["2"]["source"] == "Source B"


class TestEstimateTokens:
    """Tests for token estimation"""

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_estimate_tokens_basic(self, mock_client, mock_curator, mock_frame_mgr):
        """Should estimate tokens from context"""
        synthesizer = NarrativeSynthesizer()
        context = {"articles": [{"content": "a" * 100}], "memory": "b" * 100}

        result = synthesizer._estimate_tokens(context)

        assert result > 0

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_estimate_tokens_empty_context(self, mock_client, mock_curator, mock_frame_mgr):
        """Should handle empty context"""
        synthesizer = NarrativeSynthesizer()

        result = synthesizer._estimate_tokens({})

        assert result >= 0


class TestHashProfile:
    """Tests for profile hashing"""

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_hash_profile_consistent(self, mock_client, mock_curator, mock_frame_mgr):
        """Same profile should produce same hash"""
        synthesizer = NarrativeSynthesizer()
        profile = {"location": "Fairfax", "domains": ["cyber"]}

        assert synthesizer._hash_profile(profile) == synthesizer._hash_profile(profile)

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_hash_profile_different_for_different_profiles(
        self, mock_client, mock_curator, mock_frame_mgr
    ):
        """Different profiles should produce different hashes"""
        synthesizer = NarrativeSynthesizer()

        hash1 = synthesizer._hash_profile({"location": "Fairfax"})
        hash2 = synthesizer._hash_profile({"location": "Arlington"})

        assert hash1 != hash2

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    def test_hash_profile_none_returns_none(self, mock_client, mock_curator, mock_frame_mgr):
        """None profile should return 'none'"""
        synthesizer = NarrativeSynthesizer()

        assert synthesizer._hash_profile(None) == "none"


class TestSynthesizeNoArticles:
    """Tests for synthesize with no available articles"""

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    async def test_returns_no_articles_status(self, mock_client, mock_curator, mock_frame_mgr):
        """Should return no_articles when curator finds nothing"""
        mock_curator_instance = MagicMock()
        mock_curator.return_value = mock_curator_instance
        mock_curator_instance.curate_for_narrative_synthesis = AsyncMock(
            return_value={"articles": []}
        )

        synthesizer = NarrativeSynthesizer()
        result = await synthesizer.synthesize()

        assert result["status"] == "no_articles"
        assert result["articles_analyzed"] == 0


class TestSynthesizeTwoPass:
    """Tests for the two-pass synthesis flow"""

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    @patch("src.context.synthesizer.ClaudeClient")
    async def test_clusters_articles_then_synthesizes(
        self, mock_client, mock_curator, mock_frame_mgr
    ):
        """Should run clustering (Pass 1) then situation synthesis (Pass 2)"""
        # Setup curator with test articles
        test_articles = [
            {
                "id": i,
                "title": f"Article {i}",
                "source": f"Source {i}",
                "content": f"Content {i}",
                "published_date": "2026-01-15",
                "url": f"https://example.com/{i}",
            }
            for i in range(1, 6)
        ]
        mock_curator_instance = MagicMock()
        mock_curator.return_value = mock_curator_instance
        mock_curator_instance.curate_for_narrative_synthesis = AsyncMock(
            return_value={"articles": test_articles}
        )
        mock_curator_instance._format_user_profile = MagicMock(return_value={})
        mock_curator_instance._get_synthesis_instructions = MagicMock(return_value="")

        # Setup Claude responses
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Pass 1: clustering response
        clustering_response = json.dumps(
            {
                "clusters": [
                    {"title": "Topic A", "article_ids": [1, 2, 3], "keywords": ["topic", "a"]},
                    {"title": "Topic B", "article_ids": [4], "keywords": ["topic", "b"]},
                    {"title": "Topic C", "article_ids": [5], "keywords": ["topic", "c"]},
                ]
            }
        )

        # Pass 2: situation response (for Topic A, the only cluster with 3+ articles)
        situation_response = json.dumps(
            {
                "title": "Topic A situation",
                "narrative": "Examined narrative about Topic A.",
                "actors": [
                    {
                        "name": "Actor 1",
                        "role": "Role",
                        "interests": "Interests",
                        "epistemic_status": "reported_fact",
                    }
                ],
                "power_dynamics": {"who_benefits": "X", "who_is_harmed": "Y", "who_decides": "Z"},
                "coverage_frame": {
                    "dominant_frame": "Frame",
                    "assumed_premise": "Premise",
                    "de_emphasized": "Hidden",
                },
                "causal_structure": {"forces": "F", "constraints": "C", "dependencies": "D"},
                "information_gaps": [],
                "article_citations": [1, 2, 3],
            }
        )

        # Thin coverage response
        thin_response = json.dumps(
            {
                "thin_coverage": [
                    {
                        "title": "Topic B",
                        "article_count": 1,
                        "sources": ["Source 4"],
                        "note": "Insufficient coverage",
                    },
                    {
                        "title": "Topic C",
                        "article_count": 1,
                        "sources": ["Source 5"],
                        "note": "Insufficient coverage",
                    },
                ]
            }
        )

        # Mock analyze calls in order: clustering, situation, thin
        mock_client_instance.analyze = AsyncMock(side_effect=[clustering_response, thin_response])
        mock_client_instance.analyze_with_context = AsyncMock(return_value=situation_response)

        # Mock frame manager to return no existing clusters
        mock_frame_mgr_instance = MagicMock()
        mock_frame_mgr.return_value = mock_frame_mgr_instance
        mock_frame_mgr_instance.find_matching_cluster.return_value = None
        mock_frame_mgr_instance.discover_frames = AsyncMock(return_value=None)

        synthesizer = NarrativeSynthesizer()
        result = await synthesizer.synthesize(hours=24, max_articles=10)

        assert result["status"] == "success"
        assert result["articles_analyzed"] == 5

        synthesis_data = result["synthesis_data"]
        assert len(synthesis_data["situations"]) == 1
        assert synthesis_data["situations"][0]["title"] == "Topic A situation"
        assert len(synthesis_data["thin_coverage"]) == 2
        assert synthesis_data["metadata"]["clusters_total"] == 3
        assert synthesis_data["metadata"]["clusters_analyzed"] == 1
        assert synthesis_data["metadata"]["clusters_thin"] == 2
        assert synthesis_data["metadata"]["analysis_threshold"] == "2+ articles"
