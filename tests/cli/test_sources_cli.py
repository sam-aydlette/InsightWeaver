"""
Tests for the `sources` CLI command.

Rewritten by backlog task 012. The previous suite tested ``_compute_calibration``,
which derived a frame-uniqueness and gap-filling score per feed from the
``article_frames`` mapping and recorded ``frame_gaps``. Task 012 deleted
narrative frames, so those signals have no inputs and the command now reports
the feed inventory and the corpus each feed actually contributed.

The assertions below are deliberately about counts rather than scores: a count
is measured, and the command no longer derives anything it cannot measure.
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest

from src.cli.sources import _feed_stats, sources_command
from src.database.models import Article, RSSFeed


def _patch_db(session):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    return patch("src.cli.sources.get_db", _ctx)


@pytest.fixture
def feed_session(test_session):
    """Two feeds: A has carried three articles, B has carried none."""
    feed_a = RSSFeed(url="https://a.com/feed", name="Feed A", category="policy")
    feed_b = RSSFeed(url="https://b.com/feed", name="Feed B", category="tech")
    test_session.add_all([feed_a, feed_b])
    test_session.flush()

    test_session.add_all(
        [
            Article(feed_id=feed_a.id, guid="a1", title="A1", published_date=datetime(2026, 8, 1)),
            Article(feed_id=feed_a.id, guid="a2", title="A2", published_date=datetime(2026, 8, 20)),
            Article(feed_id=feed_a.id, guid="a3", title="A3", published_date=datetime(2026, 8, 10)),
        ]
    )
    test_session.commit()
    return test_session, feed_a, feed_b


class TestFeedStats:
    def test_no_feeds(self, test_session):
        assert _feed_stats(test_session) == {}

    def test_counts_articles_per_feed(self, feed_session):
        session, feed_a, feed_b = feed_session
        stats = _feed_stats(session)

        assert stats[feed_a.id]["articles"] == 3
        assert stats[feed_b.id]["articles"] == 0

    def test_reports_the_newest_article_not_the_last_inserted(self, feed_session):
        """The newest published date, so an out-of-order backfill does not lie."""
        session, feed_a, _ = feed_session

        assert _feed_stats(session)[feed_a.id]["latest"] == datetime(2026, 8, 20)

    def test_a_silent_feed_is_present_with_zero_rather_than_absent(self, feed_session):
        """
        A configured feed that has stored nothing is the finding, so it has a
        row. Dropping it would make "carried nothing" and "not configured"
        indistinguishable.
        """
        session, _, feed_b = feed_session
        stats = _feed_stats(session)

        assert feed_b.id in stats
        assert stats[feed_b.id]["latest"] is None


class TestSourcesList:
    def test_list_renders_feeds_and_counts(self, cli_runner, feed_session):
        session, _, _ = feed_session
        with _patch_db(session):
            result = cli_runner.invoke(sources_command, ["list"])

        assert result.exit_code == 0
        assert "Feed A" in result.output
        assert "Feed B" in result.output
        assert "3 article(s)" in result.output
        assert "no stored articles" in result.output

    def test_list_reports_no_frame_derived_scores(self, cli_runner, feed_session):
        """The deleted signals are gone from the output, not renamed."""
        session, _, _ = feed_session
        with _patch_db(session):
            result = cli_runner.invoke(sources_command, ["list"])

        assert "uniqueness" not in result.output
        assert "gap-filling" not in result.output

    def test_list_empty(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(sources_command, ["list"])

        assert result.exit_code == 0
        assert "No feeds configured" in result.output


class TestSourcesShow:
    def test_show_by_partial_name(self, cli_runner, feed_session):
        session, _, _ = feed_session
        with _patch_db(session):
            result = cli_runner.invoke(sources_command, ["show", "Feed A"])

        assert result.exit_code == 0
        assert "SOURCE: Feed A" in result.output
        assert "https://a.com/feed" in result.output
        assert "stored articles: 3" in result.output

    def test_show_no_match(self, cli_runner, feed_session):
        session, _, _ = feed_session
        with _patch_db(session):
            result = cli_runner.invoke(sources_command, ["show", "Nonexistent"])

        assert result.exit_code == 0
        assert "No feed matching" in result.output
