"""
Tests for ``insightweaver beat coverage NAME``.

What is pinned here is the gate: the exit code, and the fact that the counts
printed under it always add back up to the number of probes the beat declared.
The command is only useful if a shell can trust it, and the two ways to break
that trust are exiting 0 on a miss and exiting 0 on a run that measured nothing.

Every beat file and every article here is written by the test. No test names a
real event or reads the shipped beat's probes -- those are statements about live
corpus state, and pinning them into CI would make this suite fail for reasons
unrelated to the code under test.

Also pinned: the command runs with no ANTHROPIC_API_KEY and never writes.
"""

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.cli.beat import (
    EXIT_NOTHING_MEASURED,
    EXIT_OK,
    EXIT_UNMATCHED,
    beat_command,
)
from src.config.beats import load_beat
from src.config.feed_matcher import Feed
from src.database.models import Article, Base, RSSFeed

FEED_URL = "https://example.test/in-beat"
FEED_NAME = "In-Beat Wire"

MATCHING_PROBE = {
    "date": "2026-08-24",
    "what": "the thing that happened",
    "terms": ["FedRAMP"],
    "any_of": [["director", "administrator"], ["reinstat*", "restored"]],
}
MISSING_PROBE = {
    "date": "2026-08-24",
    "what": "the thing nobody carried",
    "terms": ["CMMC"],
    "any_of": [["phase 2", "phase two"]],
}
OLD_PROBE = {
    "date": "2019-01-15",
    "what": "the thing that predates the corpus",
    "terms": ["CISA"],
    "any_of": [["binding operational directive"]],
}


@pytest.fixture
def beats_dir(tmp_path, monkeypatch):
    """A beats directory the test owns, wired into the command."""
    directory = tmp_path / "beats"
    directory.mkdir()
    monkeypatch.setattr(
        "src.cli.beat.load_beat", lambda name, beats_dir=directory: load_beat(name, beats_dir)
    )
    return directory


@pytest.fixture
def write_beat(beats_dir):
    def _write(probes, name="probe-beat"):
        (beats_dir / f"{name}.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "description": "A beat under test.",
                    "sources": [{"adapter": "rss", "feed_tags": ["regulatory"]}],
                    "coverage_probes": probes,
                }
            )
        )
        return name

    return _write


@pytest.fixture
def fake_feeds(monkeypatch):
    """One configured feed, so the beat resolves without reading config/feeds."""

    class FakeMatcher:
        all_feeds = [
            Feed(
                name=FEED_NAME,
                url=FEED_URL,
                scope=[],
                geo_tags=[],
                domain_tags=["regulatory"],
                specialty_tags=[],
                relevance_score=0.9,
                source_file="fake.json",
            )
        ]

    monkeypatch.setattr("src.config.beats.FeedMatcher", FakeMatcher)


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """
    A throwaway database wired into the command, plus a helper to fill it.

    ``SessionLocal`` is replaced rather than the global engine so that no test
    here depends on whatever DATABASE_URL happens to name.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'coverage.db'}")
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine)
    monkeypatch.setattr("src.cli.beat.SessionLocal", maker)

    session = maker()
    feed = RSSFeed(url=FEED_URL, name=FEED_NAME, category="test")
    session.add(feed)
    session.commit()

    def add(title, when=datetime(2026, 8, 25)):
        session.add(
            Article(
                feed_id=feed.id,
                guid=f"guid-{title}",
                title=title,
                description="",
                normalized_content="",
                published_date=when,
            )
        )
        session.commit()

    add.session = session
    add.engine = engine
    yield add
    session.close()


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """The command must work with no key at all; this is not optional."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def invoke(cli_runner, name):
    return cli_runner.invoke(beat_command, ["coverage", name])


class TestTheGate:
    def test_all_probes_matched_exits_zero(self, cli_runner, write_beat, fake_feeds, corpus):
        corpus("FedRAMP director reinstated after review")
        result = invoke(cli_runner, write_beat([MATCHING_PROBE]))

        assert result.exit_code == EXIT_OK
        assert "[MATCHED]" in result.output
        assert "PASS" in result.output

    def test_an_unmatched_probe_exits_non_zero(self, cli_runner, write_beat, fake_feeds, corpus):
        corpus("An unrelated procurement notice")
        result = invoke(cli_runner, write_beat([MISSING_PROBE]))

        assert result.exit_code == EXIT_UNMATCHED
        assert result.exit_code != 0
        assert "[UNMATCHED]" in result.output
        assert "FAIL" in result.output

    def test_one_miss_among_matches_still_fails(self, cli_runner, write_beat, fake_feeds, corpus):
        corpus("FedRAMP director reinstated after review")
        result = invoke(cli_runner, write_beat([MATCHING_PROBE, MISSING_PROBE]))

        assert result.exit_code == EXIT_UNMATCHED
        assert "[MATCHED]" in result.output
        assert "[UNMATCHED]" in result.output

    def test_a_beat_with_no_probes_is_not_a_pass(self, cli_runner, write_beat, fake_feeds, corpus):
        """
        An undeclared probe set is the state the beat was in when it missed the
        event this feature exists because of. It must not exit 0.
        """
        result = invoke(cli_runner, write_beat([]))

        assert result.exit_code == EXIT_NOTHING_MEASURED
        assert "declares no coverage_probes" in result.output

    def test_every_probe_inconclusive_is_not_a_pass_either(
        self, cli_runner, write_beat, fake_feeds, corpus
    ):
        corpus("Recent unrelated news")
        result = invoke(cli_runner, write_beat([OLD_PROBE]))

        assert result.exit_code == EXIT_NOTHING_MEASURED
        assert "[INCONCLUSIVE]" in result.output
        assert "NOT MEASURED" in result.output

    def test_the_three_exit_codes_are_distinct(self):
        assert len({EXIT_OK, EXIT_UNMATCHED, EXIT_NOTHING_MEASURED}) == 3


class TestOutput:
    def test_a_match_names_the_feed_that_carried_it(
        self, cli_runner, write_beat, fake_feeds, corpus
    ):
        corpus("FedRAMP director reinstated after review")
        result = invoke(cli_runner, write_beat([MATCHING_PROBE]))
        assert FEED_NAME in result.output

    def test_an_unmatched_probe_says_what_the_closest_article_lacked(
        self, cli_runner, write_beat, fake_feeds, corpus
    ):
        corpus("CMMC rulemaking continues")
        result = invoke(cli_runner, write_beat([MISSING_PROBE]))
        assert "phase 2" in result.output

    def test_an_inconclusive_probe_says_why(self, cli_runner, write_beat, fake_feeds, corpus):
        corpus("Recent unrelated news")
        result = invoke(cli_runner, write_beat([OLD_PROBE]))
        assert "predates the corpus" in result.output

    def test_the_denominator_is_every_probe_declared(
        self, cli_runner, write_beat, fake_feeds, corpus
    ):
        """
        The inconclusive probe stays in the count. A suite that decayed to only
        the probes still matching would print '1 matched ... of 1 declared'.
        """
        corpus("FedRAMP director reinstated after review")
        result = invoke(cli_runner, write_beat([MATCHING_PROBE, OLD_PROBE]))

        assert "1 matched + 0 unmatched + 1 inconclusive of 2 probe(s) declared" in result.output
        assert result.exit_code == EXIT_OK
        assert "counted above, not dropped" in result.output

    def test_show_problems_hides_the_passes_only(self, cli_runner, write_beat, fake_feeds, corpus):
        corpus("FedRAMP director reinstated after review")
        result = cli_runner.invoke(
            beat_command,
            ["coverage", write_beat([MATCHING_PROBE, OLD_PROBE]), "--show", "problems"],
        )
        assert "the thing that happened" not in result.output
        assert "the thing that predates the corpus" in result.output
        assert "of 2 probe(s) declared" in result.output


class TestFailures:
    def test_an_unknown_beat_is_an_error_not_a_pass(self, cli_runner, beats_dir, corpus):
        result = invoke(cli_runner, "no-such-beat")
        assert result.exit_code != 0
        assert "No beat named" in result.output

    def test_an_invalid_probe_block_is_reported_by_name(self, cli_runner, beats_dir, corpus):
        (beats_dir / "broken.json").write_text(
            json.dumps(
                {
                    "name": "broken",
                    "sources": [{"adapter": "rss", "feed_tags": ["regulatory"]}],
                    "coverage_probes": [{"date": "2026-08-24", "what": "x", "terms": ["FedRAMP"]}],
                }
            )
        )
        result = invoke(cli_runner, "broken")
        assert result.exit_code != 0
        assert "single term" in result.output


class TestItNeverWrites:
    def test_the_corpus_is_unchanged_by_a_run(self, cli_runner, write_beat, fake_feeds, corpus):
        corpus("FedRAMP director reinstated after review")
        corpus("An unrelated procurement notice")
        before = corpus.session.query(Article).count()

        invoke(cli_runner, write_beat([MATCHING_PROBE, MISSING_PROBE, OLD_PROBE]))

        corpus.session.expire_all()
        assert corpus.session.query(Article).count() == before

    def test_the_command_never_commits(
        self, cli_runner, write_beat, fake_feeds, corpus, monkeypatch
    ):
        """
        The corpus is shared. Committing nothing is still an intent to write, so
        the read path must not reach for commit at all.
        """
        maker = sessionmaker(bind=corpus.engine)
        commits = []

        class Watched(maker.class_):
            def commit(self, *args, **kwargs):
                commits.append(True)
                raise AssertionError("beat coverage must not commit")

        monkeypatch.setattr(
            "src.cli.beat.SessionLocal", sessionmaker(bind=corpus.engine, class_=Watched)
        )
        corpus("FedRAMP director reinstated after review")

        result = invoke(cli_runner, write_beat([MATCHING_PROBE]))

        assert commits == []
        assert result.exit_code == EXIT_OK
