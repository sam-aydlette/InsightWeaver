"""
Tests for `insightweaver brief --beat`.

Three things are pinned here:

* the beat reaches the pipeline, and only after being loaded and validated;
* a bad ``--beat`` costs nothing -- the pipeline is never started;
* **the no-beat default path is unchanged** -- ``brief`` with no ``--beat``
  still calls ``run_pipeline`` with exactly the arguments it did before, plus
  an explicit ``beat=None``, and the render-only ``--from-run`` path is
  untouched.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.cli.brief import brief_group


@pytest.fixture
def api_key(monkeypatch):
    settings = MagicMock()
    settings.anthropic_api_key = "test-api-key"
    monkeypatch.setattr("src.cli.brief.settings", settings)
    return settings


@pytest.fixture
def pipeline_spy(monkeypatch):
    """Capture the run_pipeline call and return a run that found nothing."""
    calls = []

    async def _spy(**kwargs):
        calls.append(kwargs)
        return {
            "stages": {"synthesis": {"status": "no_articles", "articles_analyzed": 0}},
            "summary": {"duration_seconds": 0.0, "articles_fetched": 0},
        }

    monkeypatch.setattr("src.cli.brief.run_pipeline", _spy)
    return calls


@pytest.fixture
def beat_ready_engine(tmp_path, monkeypatch):
    """
    A throwaway database that has already run the beats migration.

    Bound explicitly so no test in this module depends on whatever
    DATABASE_URL happens to name.
    """
    from sqlalchemy import create_engine

    from src.database.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'beat-ready.db'}")
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("src.cli.brief.engine", engine)
    return engine


@pytest.fixture
def pipeline_fuse(monkeypatch):
    """Blow up if the pipeline is reached at all."""

    async def _fuse(*args, **kwargs):
        raise AssertionError("the pipeline must not start")

    monkeypatch.setattr("src.cli.brief.run_pipeline", _fuse)


@pytest.fixture
def beat_on_disk(tmp_path, monkeypatch):
    """A valid beat in a throwaway beats directory."""
    directory = tmp_path / "beats"
    directory.mkdir()
    (directory / "test-beat.json").write_text(
        json.dumps(
            {
                "name": "test-beat",
                "description": "A test beat.",
                "sources": [{"adapter": "rss", "feed_tags": ["regulatory"]}],
                "coverage": {},
                "standing_questions": [],
                "channels": ["terminal"],
            }
        )
    )
    monkeypatch.setattr("src.config.beats.DEFAULT_BEATS_DIR", directory)
    return directory


@pytest.fixture
def malformed_beat_on_disk(tmp_path, monkeypatch):
    directory = tmp_path / "beats"
    directory.mkdir()
    (directory / "broken-beat.json").write_text("{ this is not json")
    monkeypatch.setattr("src.config.beats.DEFAULT_BEATS_DIR", directory)
    return directory


class TestNoBeatIsTheDefaultPath:
    def test_run_pipeline_called_exactly_as_before(self, cli_runner, api_key, pipeline_spy):
        result = cli_runner.invoke(brief_group, [], obj={})

        assert result.exit_code == 0, result.output
        assert pipeline_spy == [{"prioritize_hours": 24, "topic_filters": {}, "beat": None}]

    def test_topic_filters_still_reach_the_pipeline(self, cli_runner, api_key, pipeline_spy):
        result = cli_runner.invoke(brief_group, ["-cs", "-n", "--hours", "48"], obj={})

        assert result.exit_code == 0, result.output
        assert pipeline_spy == [
            {
                "prioritize_hours": 48,
                "topic_filters": {"topics": ["cybersecurity"], "scopes": ["national"]},
                "beat": None,
            }
        ]

    def test_no_beat_never_touches_the_beats_directory(
        self, cli_runner, api_key, pipeline_spy, monkeypatch
    ):
        """The default brief must not depend on config/beats/ existing at all."""

        def _explode(*args, **kwargs):
            raise AssertionError("the default path must not load a beat")

        monkeypatch.setattr("src.cli.brief.load_beat", _explode)

        result = cli_runner.invoke(brief_group, [], obj={})

        assert result.exit_code == 0, result.output


class TestBeatReachesThePipeline:
    def test_loaded_beat_is_passed_through(
        self, cli_runner, api_key, pipeline_spy, beat_on_disk, beat_ready_engine
    ):
        result = cli_runner.invoke(brief_group, ["--beat", "test-beat"], obj={})

        assert result.exit_code == 0, result.output
        assert len(pipeline_spy) == 1
        beat = pipeline_spy[0]["beat"]
        assert beat is not None
        assert beat.name == "test-beat"
        assert beat.sources[0].feed_tags == ("regulatory",)

    def test_empty_beat_is_reported_rather_than_rendered_blank(
        self, cli_runner, api_key, pipeline_spy, beat_on_disk, beat_ready_engine
    ):
        """A beat with nothing in it is an expected outcome, and it says so."""
        result = cli_runner.invoke(brief_group, ["--beat", "test-beat"], obj={})

        assert result.exit_code == 0, result.output
        assert "NO ARTICLES IN BEAT 'test-beat'" in result.output


class TestBadBeatCostsNothing:
    def test_unknown_beat_names_what_is_available(
        self, cli_runner, api_key, pipeline_fuse, beat_on_disk, beat_ready_engine
    ):
        result = cli_runner.invoke(brief_group, ["--beat", "nope"], obj={})

        assert result.exit_code != 0
        assert "No beat named 'nope'" in result.output
        assert "test-beat" in result.output

    def test_malformed_beat_names_the_problem(
        self, cli_runner, api_key, pipeline_fuse, malformed_beat_on_disk, beat_ready_engine
    ):
        result = cli_runner.invoke(brief_group, ["--beat", "broken-beat"], obj={})

        assert result.exit_code != 0
        assert "not valid JSON" in result.output

    def test_beat_is_resolved_before_the_api_key_matters(
        self, cli_runner, pipeline_fuse, beat_on_disk, beat_ready_engine, monkeypatch
    ):
        """A typo should not be masked by an unrelated missing-key abort."""
        settings = MagicMock()
        settings.anthropic_api_key = ""
        monkeypatch.setattr("src.cli.brief.settings", settings)

        result = cli_runner.invoke(brief_group, ["--beat", "nope"], obj={})

        assert result.exit_code != 0
        assert "No beat named 'nope'" in result.output


class TestBeatAndFromRunAreMutuallyExclusive:
    def test_rejected_before_loading_anything(self, cli_runner, monkeypatch, pipeline_fuse):
        def _explode(_id):
            raise AssertionError("--from-run must not load a brief when --beat is given")

        monkeypatch.setattr("src.cli.brief.load_stored_brief", _explode)

        result = cli_runner.invoke(
            brief_group, ["--from-run", "176", "--beat", "test-beat"], obj={}
        )

        assert result.exit_code != 0
        assert "--beat applies to the live pipeline" in result.output


class TestUnmigratedDatabaseIsRefusedNotMisreported:
    """
    A beat run on a database without the beat tables must say so, not run and
    then report "no articles" -- the wrong reason is worse than no reason.
    """

    @pytest.fixture
    def pre_beat_engine(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine

        from src.database.models import Base

        engine = create_engine(f"sqlite:///{tmp_path / 'pre-beat.db'}")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                table
                for name, table in Base.metadata.tables.items()
                if name not in ("beats", "beat_runs")
            ],
        )
        monkeypatch.setattr("src.cli.brief.engine", engine)
        return engine

    def test_beat_run_is_refused_with_the_migration_command(
        self, cli_runner, api_key, pipeline_fuse, beat_on_disk, pre_beat_engine
    ):
        result = cli_runner.invoke(brief_group, ["--beat", "test-beat"], obj={})

        assert result.exit_code != 0
        assert "add_beats" in result.output
        assert "NO ARTICLES" not in result.output

    def test_default_brief_is_unaffected(self, cli_runner, api_key, pipeline_spy, pre_beat_engine):
        result = cli_runner.invoke(brief_group, [], obj={})

        assert result.exit_code == 0, result.output
        assert pipeline_spy == [{"prioritize_hours": 24, "topic_filters": {}, "beat": None}]
