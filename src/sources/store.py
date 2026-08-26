"""
Persisting adapter output into the existing ``articles`` table.

There is no new table and no new column. A non-RSS source gets an ordinary
``rss_feeds`` row -- that table is the *sources* table in everything but name,
and it is what ``Article.feed_id`` points at, what beat scoping filters on
(``src/context/curator.py``), and what the citation map reads a source name
from. Giving Federal Register its own table would have required touching every
one of those, which is precisely the rewrite backlog task 005 exists to avoid.

Dedup is the ``(feed_id, guid)`` unique constraint that already exists on
``articles``. Adapters over structured APIs set ``guid`` to a content hash, so
re-running over unchanged upstream content inserts zero rows. Proven in
tests/sources/test_dedup.py rather than assumed.

Added 2026-08-26 for backlog task 005.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy.orm import Session

from ..database.models import Article, RSSFeed
from ..utils import utcnow
from .base import RawItem

logger = logging.getLogger(__name__)


def ensure_source(db: Session, name: str, url: str, category: str) -> RSSFeed:
    """
    Get or create the source row for an adapter, keyed by URL.

    Keyed by URL because that is the column with the unique constraint and the
    key beat scoping resolves against (``RSSFeed.url.in_(beat_feed_urls)``).
    """
    row = db.query(RSSFeed).filter(RSSFeed.url == url).first()
    if row is None:
        row = RSSFeed(name=name, url=url, category=category, is_active=True)
        db.add(row)
        db.flush()
        logger.info(f"Registered source '{name}' as feed_id {row.id}")
    else:
        # These columns are declared with the pre-2.0 Column() style, which mypy
        # reads as Column[str] rather than str; the assignments are correct at
        # runtime. Same reason src.database.* is excluded from mypy entirely.
        row.name = name  # type: ignore[assignment]
        row.category = category  # type: ignore[assignment]
    return row


def store_items(db: Session, source: RSSFeed, items: Iterable[RawItem]) -> tuple[int, int]:
    """
    Insert items that this source has not already stored.

    Returns ``(inserted, duplicates)``. Duplicates are found two ways: an
    existing row with the same ``(feed_id, guid)``, and a repeat within this
    batch (two Federal Register queries can return the same document). The
    ``_feed_guid_uc`` constraint is left as the backstop -- if it ever fires,
    something concurrent wrote the same guid and the caller should hear about
    it as an error rather than have it counted as a duplicate and forgotten.
    """
    inserted = 0
    duplicates = 0

    seen_in_batch: set[str] = set()
    for item in items:
        fields = item.as_article_fields()
        guid = fields["guid"]
        if not guid or not fields["title"]:
            continue
        if guid in seen_in_batch:
            duplicates += 1
            continue
        seen_in_batch.add(guid)

        existing = (
            db.query(Article.id).filter(Article.feed_id == source.id, Article.guid == guid).first()
        )
        if existing is not None:
            duplicates += 1
            continue

        db.add(Article(feed_id=source.id, **fields))
        db.flush()
        inserted += 1

    source.last_fetched = utcnow()  # type: ignore[assignment]
    source.last_error = None  # type: ignore[assignment]
    source.error_count = 0  # type: ignore[assignment]
    return inserted, duplicates


def source_article_count(db: Session, source: RSSFeed) -> int:
    """How many articles this source has ever contributed."""
    return int(db.query(Article.id).filter(Article.feed_id == source.id).count())
