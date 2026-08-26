"""
Tests for Two-Pass Narrative Synthesizer
"""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from src.context.synthesizer import NarrativeSynthesizer


def _stub_client() -> MagicMock:
    """A client double that carries the attributes the real one does.

    ``.model`` matters: the synthesizer records it as provenance on every
    AnalysisRun, so a double without it lets a bug reach the database that
    the real object would have caught. Added 2026-08-26.
    """
    client = MagicMock()
    client.model = "claude-sonnet-5"
    return client


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

        NarrativeSynthesizer(topic_filters=filters, client=_stub_client())

        # beat=None is the default path: the curator is told there is no beat,
        # which leaves its article selection exactly as it was before beats.
        mock_curator.assert_called_with(topic_filters=filters, beat=None)


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

        synthesizer = NarrativeSynthesizer(client=_stub_client())
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
        mock_client_instance.model = "claude-sonnet-5"

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


class TestBeatRunIsRecorded:
    """
    A beat run must leave a ``beat_runs`` row attributing the synthesis, and a
    non-beat run must leave none. That row is the whole basis of beat scoping:
    the graph tables carry no beat_id, so an unattributed run is
    indistinguishable from the default brief.

    Added 2026-08-26 with the beat abstraction (backlog task 004).
    """

    CLUSTERING = json.dumps(
        {"clusters": [{"title": "Rulemaking", "article_ids": [1, 2], "keywords": ["rule"]}]}
    )
    SITUATION = json.dumps(
        {
            "title": "A rulemaking situation",
            "narrative": "Narrative.",
            "actors": [],
            "power_dynamics": {"who_benefits": "X", "who_is_harmed": "Y", "who_decides": "Z"},
            "coverage_frame": {
                "dominant_frame": "F",
                "assumed_premise": "P",
                "de_emphasized": "D",
            },
            "causal_structure": {"forces": "F", "constraints": "C", "dependencies": "D"},
            "information_gaps": [],
            "article_citations": [1, 2],
        }
    )

    @staticmethod
    def _beat_config():
        from src.config.beats import BeatConfig, BeatSource

        return BeatConfig(
            name="test-beat",
            description="A test beat.",
            sources=(BeatSource(adapter="rss", feed_tags=("regulatory",)),),
            coverage={},
            standing_questions=(),
            channels=("terminal",),
            config_path="config/beats/test-beat.json",
        )

    def _wire(self, mock_curator, mock_frame_mgr):
        """Curator, frame manager and Claude client doubles for one run."""
        articles = [
            {
                "id": i,
                "title": f"Article {i}",
                "source": f"Source {i}",
                "content": f"Content {i}",
                "published_date": "2026-08-20",
                "url": f"https://example.com/{i}",
            }
            for i in (1, 2)
        ]
        curator = MagicMock()
        mock_curator.return_value = curator
        curator.curate_for_narrative_synthesis = AsyncMock(return_value={"articles": articles})
        curator._format_user_profile = MagicMock(return_value={})
        curator._get_synthesis_instructions = MagicMock(return_value="")
        # The curator is the component that resolves a beat's feed set; the
        # synthesizer only records how big it was.
        curator.beat_feed_urls = ["https://in-beat.test/feed"]

        frame_mgr = MagicMock()
        mock_frame_mgr.return_value = frame_mgr
        frame_mgr.find_matching_cluster.return_value = None
        frame_mgr.discover_frames = AsyncMock(return_value=None)

        client = MagicMock()
        client.model = "claude-sonnet-5"
        client.analyze = AsyncMock(side_effect=[self.CLUSTERING, json.dumps({})])
        client.analyze_with_context = AsyncMock(return_value=self.SITUATION)
        return client

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_beat_run_attributes_the_synthesis(
        self, mock_curator, mock_frame_mgr, isolated_db, test_session
    ):
        from src.database.models import Beat, BeatRun

        client = self._wire(mock_curator, mock_frame_mgr)
        beat = self._beat_config()

        synthesizer = NarrativeSynthesizer(client=client, beat=beat)
        result = await synthesizer.synthesize(hours=24, max_articles=10)

        assert result["status"] == "success"

        beat_row = test_session.query(Beat).filter(Beat.name == "test-beat").one()
        assert beat_row.config_path == "config/beats/test-beat.json"

        beat_run = test_session.query(BeatRun).one()
        assert beat_run.beat_id == beat_row.id
        assert beat_run.synthesis_id == result["synthesis_id"]
        assert beat_run.articles_analyzed == 2
        assert beat_run.feeds_resolved == 1

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_run_without_a_beat_records_nothing(
        self, mock_curator, mock_frame_mgr, isolated_db, test_session
    ):
        from src.database.models import Beat, BeatRun

        client = self._wire(mock_curator, mock_frame_mgr)

        synthesizer = NarrativeSynthesizer(client=client)
        result = await synthesizer.synthesize(hours=24, max_articles=10)

        assert result["status"] == "success"
        assert synthesizer.beat_id is None
        assert test_session.query(BeatRun).count() == 0
        assert test_session.query(Beat).count() == 0

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_repeated_beat_runs_reuse_one_beat_row(
        self, mock_curator, mock_frame_mgr, isolated_db, test_session
    ):
        from src.database.models import Beat, BeatRun

        beat = self._beat_config()
        for _ in range(2):
            client = self._wire(mock_curator, mock_frame_mgr)
            await NarrativeSynthesizer(client=client, beat=beat).synthesize(
                hours=24, max_articles=10
            )

        assert test_session.query(Beat).count() == 1
        assert test_session.query(BeatRun).count() == 2


class TestInstitutionalActivityIsRecorded:
    """
    A beat that declares coverage entities gets a mention row per entity per
    run and an activity block in the stored synthesis metadata; a beat that
    declares none gets neither, and neither does the default brief.

    The counting itself is deterministic alias matching -- no Claude call is
    made on this path, which is why the mocked client below is never asked for
    one beyond the two calls the synthesis already makes.

    Added 2026-08-26 with institutional activity (backlog task 006).
    """

    CLUSTERING = TestBeatRunIsRecorded.CLUSTERING
    SITUATION = TestBeatRunIsRecorded.SITUATION

    @staticmethod
    def _beat_config(entities):
        from src.config.beats import BeatConfig, BeatSource

        return BeatConfig(
            name="test-beat",
            description="A test beat.",
            sources=(BeatSource(adapter="rss", feed_tags=("regulatory",)),),
            coverage={},
            standing_questions=(),
            channels=("terminal",),
            config_path="config/beats/test-beat.json",
            entities=entities,
        )

    def _wire(self, mock_curator, mock_frame_mgr, contents):
        articles = [
            {
                "id": i,
                "title": f"Article {i}",
                "source": f"Source {i}",
                "content": content,
                "published_date": "2026-08-20",
                "url": f"https://example.com/{i}",
            }
            for i, content in enumerate(contents, 1)
        ]
        curator = MagicMock()
        mock_curator.return_value = curator
        curator.curate_for_narrative_synthesis = AsyncMock(return_value={"articles": articles})
        curator._format_user_profile = MagicMock(return_value={})
        curator._get_synthesis_instructions = MagicMock(return_value="")
        curator.beat_feed_urls = ["https://in-beat.test/feed"]

        frame_mgr = MagicMock()
        mock_frame_mgr.return_value = frame_mgr
        frame_mgr.find_matching_cluster.return_value = None
        frame_mgr.discover_frames = AsyncMock(return_value=None)

        client = MagicMock()
        client.model = "claude-sonnet-5"
        client.analyze = AsyncMock(side_effect=[self.CLUSTERING, json.dumps({})])
        client.analyze_with_context = AsyncMock(return_value=self.SITUATION)
        return client

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_mentions_are_written_in_the_synthesis_transaction(
        self, mock_curator, mock_frame_mgr, isolated_db, test_session
    ):
        from src.config.beats import CoverageEntity
        from src.database.models import BeatEntity, BeatRun, EntityMention

        client = self._wire(
            mock_curator, mock_frame_mgr, ["CISA issued an advisory.", "Nothing relevant."]
        )
        beat = self._beat_config((CoverageEntity("org", "CISA"), CoverageEntity("program", "CMMC")))

        result = await NarrativeSynthesizer(client=client, beat=beat).synthesize(
            hours=24, max_articles=10
        )

        assert result["status"] == "success"
        assert test_session.query(BeatEntity).count() == 2

        beat_run = test_session.query(BeatRun).one()
        mentions = test_session.query(EntityMention).all()
        # Both entities get a row, including the one that counted zero.
        assert {m.item_count for m in mentions} == {0, 1}
        assert all(m.beat_run_id == beat_run.id for m in mentions)
        assert all(m.synthesis_id == result["synthesis_id"] for m in mentions)
        assert all(m.items_scanned == 2 for m in mentions)

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_the_brief_metadata_reports_the_delta_not_a_tally(
        self, mock_curator, mock_frame_mgr, isolated_db, test_session
    ):
        from src.config.beats import CoverageEntity

        beat = self._beat_config((CoverageEntity("org", "CISA"),))

        # Three quiet runs establish a baseline, then CISA appears twice.
        for contents in (["Nothing."], ["Nothing."], ["Nothing."]):
            client = self._wire(mock_curator, mock_frame_mgr, contents * 2)
            await NarrativeSynthesizer(client=client, beat=beat).synthesize(
                hours=24, max_articles=10
            )

        client = self._wire(mock_curator, mock_frame_mgr, ["CISA acted.", "CISA again."])
        result = await NarrativeSynthesizer(client=client, beat=beat).synthesize(
            hours=24, max_articles=10
        )

        activity = result["synthesis_data"]["metadata"]["institutional_activity"]
        assert activity["entities"] == [
            {
                "kind": "org",
                "name": "CISA",
                "count": 2,
                "trailing_average": 0.0,
                "prior_runs": 3,
                "movement": "up",
            }
        ]

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_a_beat_without_coverage_records_nothing(
        self, mock_curator, mock_frame_mgr, isolated_db, test_session
    ):
        from src.database.models import BeatEntity, EntityMention

        client = self._wire(mock_curator, mock_frame_mgr, ["CISA acted.", "More."])

        result = await NarrativeSynthesizer(client=client, beat=self._beat_config(())).synthesize(
            hours=24, max_articles=10
        )

        assert "institutional_activity" not in result["synthesis_data"]["metadata"]
        assert test_session.query(BeatEntity).count() == 0
        assert test_session.query(EntityMention).count() == 0

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_the_default_brief_records_nothing(
        self, mock_curator, mock_frame_mgr, isolated_db, test_session
    ):
        from src.database.models import BeatEntity, EntityMention

        client = self._wire(mock_curator, mock_frame_mgr, ["CISA acted.", "More."])

        result = await NarrativeSynthesizer(client=client).synthesize(hours=24, max_articles=10)

        assert "institutional_activity" not in result["synthesis_data"]["metadata"]
        assert test_session.query(BeatEntity).count() == 0
        assert test_session.query(EntityMention).count() == 0

    @pytest.mark.asyncio
    @patch("src.context.synthesizer.FrameManager")
    @patch("src.context.synthesizer.ContextCurator")
    async def test_a_database_without_the_tables_loses_the_section_not_the_brief(
        self, mock_curator, mock_frame_mgr, isolated_db, test_engine, test_session
    ):
        """
        The activity pass is an additive reading of articles the run already
        has. On a database that predates the migration it is skipped with a
        warning; losing a whole brief over one section would be the worse
        outcome, and the run's own attribution is unaffected.
        """
        from src.config.beats import CoverageEntity
        from src.database.models import BeatEntity, BeatRun, EntityMention

        EntityMention.__table__.drop(test_engine)
        BeatEntity.__table__.drop(test_engine)

        client = self._wire(mock_curator, mock_frame_mgr, ["CISA acted.", "More."])
        beat = self._beat_config((CoverageEntity("org", "CISA"),))

        result = await NarrativeSynthesizer(client=client, beat=beat).synthesize(
            hours=24, max_articles=10
        )

        assert result["status"] == "success"
        assert "institutional_activity" not in result["synthesis_data"]["metadata"]
        assert test_session.query(BeatRun).count() == 1
