"""
Tests for the `diet` CLI command.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.cli.diet import diet_command
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

    return patch("src.cli.diet.get_db", _ctx)


@pytest.fixture
def diet_session(test_session):
    """Two feeds, two frames, articles classified so feed A carries both
    frames and feed B carries only one (shared) frame."""
    feed_a = RSSFeed(url="https://a.com/feed", name="Feed A")
    feed_b = RSSFeed(url="https://b.com/feed", name="Feed B")
    test_session.add_all([feed_a, feed_b])
    test_session.flush()

    tc = TopicCluster(name="fed policy", keywords=["fed"])
    test_session.add(tc)
    test_session.flush()

    hawk = NarrativeFrame(topic_cluster_id=tc.id, label="inflation hawk frame")
    labor = NarrativeFrame(topic_cluster_id=tc.id, label="labor market frame")
    test_session.add_all([hawk, labor])
    test_session.flush()

    # Feed A: one article on hawk, one on labor.
    a1 = Article(feed_id=feed_a.id, guid="a1", title="A1")
    a2 = Article(feed_id=feed_a.id, guid="a2", title="A2")
    # Feed B: one article on labor only.
    b1 = Article(feed_id=feed_b.id, guid="b1", title="B1")
    test_session.add_all([a1, a2, b1])
    test_session.flush()

    test_session.add_all(
        [
            ArticleFrame(article_id=a1.id, frame_id=hawk.id, confidence=0.9),
            ArticleFrame(article_id=a2.id, frame_id=labor.id, confidence=0.8),
            ArticleFrame(article_id=b1.id, frame_id=labor.id, confidence=0.7),
        ]
    )

    gap = FrameGap(
        topic_cluster_id=tc.id,
        frame_label="consumer welfare frame",
        occurrences=4,
        feed_suggestion="consumer advocacy press",
    )
    test_session.add(gap)
    test_session.commit()
    return test_session


class TestFeeds:
    def test_feeds_fingerprint(self, cli_runner, diet_session):
        with _patch_db(diet_session):
            result = cli_runner.invoke(diet_command, ["feeds"])
        assert result.exit_code == 0
        assert "Feed A" in result.output
        assert "Feed B" in result.output
        assert "inflation hawk frame" in result.output
        assert "labor market frame" in result.output

    def test_feeds_empty(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(diet_command, ["feeds"])
        assert result.exit_code == 0
        assert "No frame classifications yet" in result.output


class TestGaps:
    def test_gaps_listed(self, cli_runner, diet_session):
        with _patch_db(diet_session):
            result = cli_runner.invoke(diet_command, ["gaps"])
        assert result.exit_code == 0
        assert "consumer welfare frame" in result.output
        assert "4x" in result.output
        assert "consumer advocacy press" in result.output

    def test_gaps_empty(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(diet_command, ["gaps"])
        assert result.exit_code == 0
        assert "No frame gaps recorded" in result.output


class TestOverlap:
    def test_overlap_splits_unique_and_shared(self, cli_runner, diet_session):
        with _patch_db(diet_session):
            result = cli_runner.invoke(diet_command, ["overlap"])
        assert result.exit_code == 0
        # hawk frame -> only Feed A. labor frame -> Feed A and Feed B.
        assert "inflation hawk frame" in result.output
        assert "labor market frame" in result.output
        assert "2 feeds" in result.output

    def test_overlap_empty(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(diet_command, ["overlap"])
        assert result.exit_code == 0
        assert "No frame classifications yet" in result.output
