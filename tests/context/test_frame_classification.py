"""
Tests for FrameManager article-to-frame classification (Stage 4).
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.context.frame_manager import FrameManager
from src.database.models import (
    Article,
    ArticleFrame,
    NarrativeFrame,
    RSSFeed,
    TopicCluster,
)


def _patch_db(session):
    """Patch frame_manager.get_db so its writes land in the test session."""

    @contextmanager
    def _ctx():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    return patch("src.context.frame_manager.get_db", _ctx)


@pytest.fixture
def cluster_with_frames(test_session):
    """A topic cluster with two frames and three articles in a feed."""
    feed = RSSFeed(url="https://example.com/feed", name="Example Feed")
    test_session.add(feed)
    test_session.flush()

    tc = TopicCluster(name="fed policy", keywords=["fed", "rates"])
    test_session.add(tc)
    test_session.flush()

    frame_a = NarrativeFrame(
        topic_cluster_id=tc.id, label="inflation hawk frame", description="prices first"
    )
    frame_b = NarrativeFrame(
        topic_cluster_id=tc.id, label="labor market frame", description="jobs first"
    )
    test_session.add_all([frame_a, frame_b])
    test_session.flush()

    articles = []
    for i in range(3):
        a = Article(
            feed_id=feed.id,
            guid=f"guid-{i}",
            title=f"Article {i}",
            content=f"Content for article {i}.",
        )
        test_session.add(a)
        articles.append(a)
    test_session.flush()
    test_session.commit()

    return test_session, tc, [frame_a, frame_b], articles


class TestClassifyArticlesToFrames:
    @pytest.fixture
    def manager(self, mock_claude_client):
        # FrameManager takes a client for discover_frames; classify spins up
        # its own ClaudeClient, so patch that path.
        return FrameManager(mock_claude_client)

    @pytest.mark.asyncio
    async def test_empty_inputs_write_nothing(self, manager):
        assert await manager.classify_articles_to_frames([], []) == 0

    @pytest.mark.asyncio
    async def test_classification_writes_article_frames(self, manager, cluster_with_frames, mocker):
        session, tc, frames, articles = cluster_with_frames

        article_dicts = [{"id": a.id, "title": a.title, "content": a.content} for a in articles]
        response = json.dumps(
            {
                "classifications": [
                    {"article_index": 0, "frame_label": "inflation hawk frame", "confidence": 0.9},
                    {"article_index": 1, "frame_label": "labor market frame", "confidence": 0.7},
                    # index 2 omitted -> no clear frame, should not be written
                ]
            }
        )
        mock_classifier = mocker.AsyncMock()
        mock_classifier.analyze = mocker.AsyncMock(return_value=response)
        mocker.patch("src.context.frame_manager.ClaudeClient", return_value=mock_classifier)

        with _patch_db(session):
            written = await manager.classify_articles_to_frames(article_dicts, frames)
        assert written == 2

        rows = session.query(ArticleFrame).all()
        assert len(rows) == 2
        by_article = {r.article_id: (r.frame_id, r.confidence) for r in rows}
        assert by_article[articles[0].id] == (frames[0].id, 0.9)
        assert by_article[articles[1].id] == (frames[1].id, 0.7)
        assert articles[2].id not in by_article

    @pytest.mark.asyncio
    async def test_unknown_frame_label_is_dropped(self, manager, cluster_with_frames, mocker):
        session, tc, frames, articles = cluster_with_frames
        article_dicts = [{"id": articles[0].id, "title": "t", "content": "c"}]
        response = json.dumps(
            {
                "classifications": [
                    {"article_index": 0, "frame_label": "nonexistent frame", "confidence": 0.9}
                ]
            }
        )
        mock_classifier = mocker.AsyncMock()
        mock_classifier.analyze = mocker.AsyncMock(return_value=response)
        mocker.patch("src.context.frame_manager.ClaudeClient", return_value=mock_classifier)

        with _patch_db(session):
            written = await manager.classify_articles_to_frames(article_dicts, frames)
        assert written == 0
        assert session.query(ArticleFrame).count() == 0

    @pytest.mark.asyncio
    async def test_confidence_is_clamped(self, manager, cluster_with_frames, mocker):
        session, tc, frames, articles = cluster_with_frames
        article_dicts = [{"id": articles[0].id, "title": "t", "content": "c"}]
        response = json.dumps(
            {
                "classifications": [
                    {"article_index": 0, "frame_label": "inflation hawk frame", "confidence": 5.0}
                ]
            }
        )
        mock_classifier = mocker.AsyncMock()
        mock_classifier.analyze = mocker.AsyncMock(return_value=response)
        mocker.patch("src.context.frame_manager.ClaudeClient", return_value=mock_classifier)

        with _patch_db(session):
            written = await manager.classify_articles_to_frames(article_dicts, frames)
        assert written == 1
        assert session.query(ArticleFrame).first().confidence == 1.0

    @pytest.mark.asyncio
    async def test_classifier_failure_writes_nothing(self, manager, cluster_with_frames, mocker):
        session, tc, frames, articles = cluster_with_frames
        article_dicts = [{"id": articles[0].id, "title": "t", "content": "c"}]
        mock_classifier = mocker.AsyncMock()
        mock_classifier.analyze = mocker.AsyncMock(side_effect=RuntimeError("down"))
        mocker.patch("src.context.frame_manager.ClaudeClient", return_value=mock_classifier)

        with _patch_db(session):
            written = await manager.classify_articles_to_frames(article_dicts, frames)
        assert written == 0


class TestParseJson:
    def test_strips_fences(self):
        assert FrameManager._parse_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bad_json_returns_empty(self):
        assert FrameManager._parse_json("not json") == {}
