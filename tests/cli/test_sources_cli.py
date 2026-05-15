"""
Tests for the `sources` CLI command and its calibration helpers.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.cli.sources import _compute_calibration, sources_command
from src.database.models import (
    Article,
    ArticleFrame,
    FrameGap,
    NarrativeFrame,
    RSSFeed,
    TopicCluster,
)


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
def calibration_session(test_session):
    """Two feeds, three frames. Feed A carries a unique frame; both share one;
    a recorded frame gap matches a label Feed B carries (Feed B fills the gap)."""
    feed_a = RSSFeed(url="https://a.com/feed", name="Feed A")
    feed_b = RSSFeed(url="https://b.com/feed", name="Feed B")
    test_session.add_all([feed_a, feed_b])
    test_session.flush()

    tc = TopicCluster(name="fed policy", keywords=["fed"])
    test_session.add(tc)
    test_session.flush()

    hawk = NarrativeFrame(topic_cluster_id=tc.id, label="inflation hawk frame")
    labor = NarrativeFrame(topic_cluster_id=tc.id, label="labor market frame")
    consumer = NarrativeFrame(topic_cluster_id=tc.id, label="consumer welfare frame")
    test_session.add_all([hawk, labor, consumer])
    test_session.flush()

    # Feed A: 2 articles, both tagged hawk (unique to A).
    a1 = Article(feed_id=feed_a.id, guid="a1", title="A1")
    a2 = Article(feed_id=feed_a.id, guid="a2", title="A2")
    # Feed B: 2 articles, one labor (shared with A nowhere -- only B), one consumer.
    b1 = Article(feed_id=feed_b.id, guid="b1", title="B1")
    b2 = Article(feed_id=feed_b.id, guid="b2", title="B2")
    test_session.add_all([a1, a2, b1, b2])
    test_session.flush()

    test_session.add_all(
        [
            ArticleFrame(article_id=a1.id, frame_id=hawk.id, confidence=0.9),
            ArticleFrame(article_id=a2.id, frame_id=hawk.id, confidence=0.8),
            ArticleFrame(article_id=b1.id, frame_id=labor.id, confidence=0.7),
            ArticleFrame(article_id=b2.id, frame_id=consumer.id, confidence=0.7),
        ]
    )

    # A recorded gap whose label matches a frame Feed B carries.
    test_session.add(
        FrameGap(
            topic_cluster_id=tc.id,
            frame_label="consumer welfare frame",
            occurrences=3,
        )
    )
    test_session.commit()
    return test_session, feed_a, feed_b


class TestComputeCalibration:
    def test_no_feeds(self, test_session):
        assert _compute_calibration(test_session) == {}

    def test_calibration_values(self, calibration_session):
        session, feed_a, feed_b = calibration_session
        cal = _compute_calibration(session)

        # Feed A: 2 tagged articles, both on a frame carried only by A.
        a = cal[feed_a.id]
        assert a["tagged_articles"] == 2
        assert a["uniqueness"] == 1.0  # all of A's tags are unique frames

        # Feed B: 2 tagged articles, on two frames -- both also unique to B.
        # gap_filling: 1 gap label total ("consumer welfare frame"), B carries it.
        b = cal[feed_b.id]
        assert b["tagged_articles"] == 2
        assert b["uniqueness"] == 1.0
        assert b["gap_filling"] == 1.0
        # Feed A doesn't carry the gap-labeled frame.
        assert a["gap_filling"] == 0.0

    def test_zero_tagged_yields_zero_uniqueness(self, test_session):
        feed = RSSFeed(url="https://x", name="Empty Feed")
        test_session.add(feed)
        test_session.commit()
        cal = _compute_calibration(test_session)
        assert cal[feed.id]["uniqueness"] == 0.0
        assert cal[feed.id]["tagged_articles"] == 0


class TestSourcesList:
    def test_list_renders_feeds(self, cli_runner, calibration_session):
        session, _, _ = calibration_session
        with _patch_db(session):
            result = cli_runner.invoke(sources_command, ["list"])
        assert result.exit_code == 0
        assert "Feed A" in result.output
        assert "Feed B" in result.output
        assert "uniqueness" in result.output
        assert "gap-filling" in result.output

    def test_list_empty(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(sources_command, ["list"])
        assert result.exit_code == 0
        assert "No feeds configured" in result.output


class TestSourcesShow:
    def test_show_by_partial_name(self, cli_runner, calibration_session):
        session, _, _ = calibration_session
        with _patch_db(session):
            result = cli_runner.invoke(sources_command, ["show", "Feed A"])
        assert result.exit_code == 0
        assert "SOURCE: Feed A" in result.output
        assert "inflation hawk frame" in result.output

    def test_show_no_match(self, cli_runner, calibration_session):
        session, _, _ = calibration_session
        with _patch_db(session):
            result = cli_runner.invoke(sources_command, ["show", "Nonexistent"])
        assert result.exit_code == 0
        assert "No feed matching" in result.output
