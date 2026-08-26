"""
Tests for Two-Pass Narrative Synthesizer
"""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from src.context.synthesizer import NarrativeSynthesizer


@pytest.fixture
def isolated_db(test_engine):
    """Point the synthesizer's get_db at the throwaway per-test SQLite file.

    Added 2026-08-25. Without this, any test that runs synthesize() end to end
    persists AnalysisRun / ContextSnapshot / NarrativeSynthesis rows into
    whatever DATABASE_URL names -- which in a developer shell is the real
    database, not a fixture. test_engine comes from tests/conftest.py and is
    already schema-complete.
    """
    Session = sessionmaker(bind=test_engine)

    @contextmanager
    def _get_db():
        db = Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    with patch("src.context.synthesizer.get_db", _get_db):
        yield


class TestSynthesizerConfiguration:
    """Tests for synthesizer configuration behavior"""

    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    def test_topic_filters_are_applied_to_curation(self, mock_curator, mock_frame_mgr):
        """Topic filters should affect which articles are included in synthesis"""
        filters = {"topics": ["cybersecurity"]}

        NarrativeSynthesizer(topic_filters=filters, client=MagicMock())

        mock_curator.assert_called_with(topic_filters=filters)


class TestCitationMap:
    """Tests for citation map building"""

    def test_builds_citation_map_from_articles(self):
        """Citation map should index articles by 1-based position"""
        articles = [
            {"id": 10, "title": "Article A", "source": "Source A", "url": "https://a.com"},
            {"id": 20, "title": "Article B", "source": "Source B", "url": "https://b.com"},
        ]

        result = NarrativeSynthesizer._build_citation_map(articles)

        assert result["1"]["title"] == "Article A"
        assert result["1"]["article_id"] == 10
        assert result["2"]["title"] == "Article B"
        assert result["2"]["source"] == "Source B"


class TestEstimateTokens:
    """Tests for token estimation"""

    def test_estimate_tokens_basic(self):
        """Should estimate tokens from context"""
        context = {"articles": [{"content": "a" * 100}], "memory": "b" * 100}

        result = NarrativeSynthesizer._estimate_tokens(context)

        assert result > 0

    def test_estimate_tokens_empty_context(self):
        """Should handle empty context"""
        result = NarrativeSynthesizer._estimate_tokens({})

        assert result >= 0


class TestHashProfile:
    """Tests for profile hashing"""

    def test_hash_profile_consistent(self):
        """Same profile should produce same hash"""
        profile = {"location": "Fairfax", "domains": ["cyber"]}

        assert NarrativeSynthesizer._hash_profile(profile) == NarrativeSynthesizer._hash_profile(
            profile
        )

    def test_hash_profile_different_for_different_profiles(self):
        """Different profiles should produce different hashes"""
        hash1 = NarrativeSynthesizer._hash_profile({"location": "Fairfax"})
        hash2 = NarrativeSynthesizer._hash_profile({"location": "Arlington"})

        assert hash1 != hash2

    def test_hash_profile_none_returns_none(self):
        """None profile should return 'none'"""
        assert NarrativeSynthesizer._hash_profile(None) == "none"


class TestSynthesizeNoArticles:
    """Tests for synthesize with no available articles"""

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_returns_no_articles_status(self, mock_curator, mock_frame_mgr, isolated_db):
        """Should return no_articles when curator finds nothing"""
        mock_curator_instance = MagicMock()
        mock_curator.return_value = mock_curator_instance
        mock_curator_instance.curate_for_narrative_synthesis = AsyncMock(
            return_value={"articles": []}
        )

        synthesizer = NarrativeSynthesizer(client=MagicMock())
        result = await synthesizer.synthesize()

        assert result["status"] == "no_articles"
        assert result["articles_analyzed"] == 0


class TestSynthesizeTwoPass:
    """Tests for the two-pass synthesis flow"""

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_clusters_articles_then_synthesizes(
        self, mock_curator, mock_frame_mgr, isolated_db
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

        # Setup Claude responses. The client is injected, so no real
        # ClaudeClient (and therefore no ANTHROPIC_API_KEY) is ever needed.
        mock_client_instance = MagicMock()

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

        synthesizer = NarrativeSynthesizer(client=mock_client_instance)
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
