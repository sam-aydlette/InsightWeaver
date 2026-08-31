"""
The existing RSS fetcher, wrapped in the adapter contract.

This module adds *no* behaviour: ``src/rss/fetcher.py`` is not modified and not
subclassed. It offers a way to *read* an RSS feed -- returning
:class:`~src.sources.base.RawItem` values instead of writing rows -- so that
RSS and the Federal Register API are the same kind of thing to any caller.

Added 2026-08-26 for backlog task 005. Corrected 2026-08-31: this used to say
the live pipeline still fetched through ``fetch_all_active_feeds`` "exactly as
before". That is no longer true and has not been since task 025 -- both it and
``RSSFetcher.fetch_and_store_feed`` now raise, because they wrote articles with
no observation and Tier 1 routing cannot see those. **This adapter, through
``src.sources.store.store_items``, is the only way an RSS article enters the
corpus.**
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..rss.fetcher import RSSFetcher
from .base import RawItem, SourceUnavailable

logger = logging.getLogger(__name__)


class RSSAdapter:
    """
    A :class:`~src.sources.base.SourceAdapter` over one RSS/Atom feed.

    Normalization is delegated to ``RSSFetcher.normalize_article`` rather than
    reimplemented, so an item read through this adapter is byte-identical to
    one the pipeline's RSS path would have stored.
    """

    def __init__(
        self,
        name: str,
        url: str,
        category: str = "uncategorized",
        fetcher: RSSFetcher | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.name = name
        self.source_url = url
        self.category = category
        self._fetcher = fetcher
        self._owns_fetcher = fetcher is None
        self._timeout = timeout
        self._max_retries = max_retries

    async def fetch(self, since: datetime) -> list[RawItem]:
        """
        Entries published at or after ``since``.

        An entry with no parseable date is kept: dropping it would be a silent
        loss, and the ``(feed_id, guid)`` constraint makes re-seeing it free.
        """
        fetcher = self._fetcher or RSSFetcher(timeout=self._timeout, max_retries=self._max_retries)
        try:
            success, feed_data, error = await fetcher.fetch_feed(self.source_url)
        finally:
            # An injected fetcher belongs to the caller and is theirs to close.
            if self._owns_fetcher:
                await fetcher.close()

        if not success or feed_data is None:
            # Could not reach or could not parse -- an error, never an empty
            # result. See src/sources/base.py's module docstring.
            raise SourceUnavailable(self.name, error or "unknown fetch failure")

        entries = getattr(feed_data, "entries", None) or []
        feed_info = getattr(feed_data, "feed", None) or {}

        items: list[RawItem] = []
        skipped = 0
        for entry in entries:
            data = fetcher.normalize_article(entry, feed_info)
            if not data.get("title") or not data.get("guid"):
                # Same guard the RSS storage path applies before insert.
                skipped += 1
                continue
            published = data.get("published_date")
            if published is not None and published < since:
                continue
            items.append(RawItem.from_normalized(data))

        logger.info(
            f"{self.name}: {len(items)} item(s) at or after {since.isoformat()} "
            f"({len(entries)} in feed, {skipped} without title or id)"
        )
        return items
