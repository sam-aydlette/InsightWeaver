"""
The source adapter contract.

An adapter answers exactly one question -- "what has this upstream published
since <when>?" -- and answers it in the shape the RSS path already produces.
It does not write to the database, does not know about beats, and does not
know what the pipeline will do with what it returns.

Two failure modes are deliberately *not* the same thing (added 2026-08-26,
backlog task 005, LANDMINES):

* **Nothing new upstream** -> return ``[]``. Legitimate and common; the
  Federal Register publishes on business days only, so a Sunday run is empty.
* **Could not reach upstream** -> raise :class:`SourceUnavailable`. A network
  error, a non-200, a changed response contract. Never an empty list, because
  an empty list is indistinguishable from "quiet day" and would produce a thin
  brief with no error -- the same silent-success failure class as a deploy
  notifier that reported green through twelve failed nights.

The zero-items *regression* check ("this source returned items yesterday and
none today") is not the adapter's job -- it needs history, so it lives in
:mod:`src.sources.runner`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

# The exact keys ``RSSFetcher.normalize_article()`` returns, which are also the
# ``articles`` columns an adapter is allowed to populate. Anything else is the
# pipeline's business, not ingestion's. tests/sources/test_base.py asserts this
# tuple against the live RSS normalizer, so a drift in either direction fails
# rather than silently writing a malformed row.
ARTICLE_FIELDS: tuple[str, ...] = (
    "guid",
    "url",
    "title",
    "description",
    "content",
    "normalized_content",
    "published_date",
    "author",
    "categories",
    "word_count",
    "language",
)

_PUNCTUATION = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")


class SourceUnavailable(RuntimeError):
    """
    Raised when an adapter could not reach or could not understand its upstream.

    This is an error, not an empty result. See the module docstring.
    """

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"Source '{source}' is unavailable: {reason}")


def normalize_for_hash(text: str) -> str:
    """
    Lowercase, strip punctuation, collapse whitespace.

    Matches ``ArticleDeduplicator._normalize_text`` so that a hash computed at
    ingestion time and a hash computed later by the deduplicator agree about
    what counts as "the same text".
    """
    if not text:
        return ""
    collapsed = _PUNCTUATION.sub("", text.lower().strip())
    return _WHITESPACE.sub(" ", collapsed).strip()


def content_hash(*parts: str) -> str:
    """
    A stable, content-derived identity for an item.

    Deliberately *not* URL-derived: the same Federal Register document is
    reachable at its ``html_url``, its short citation URL and its public
    inspection URL, so a URL key would insert the same document three times.
    Hashing the parts an adapter considers identifying makes re-fetching the
    same document a no-op, which is what makes the dedup proof in
    tests/sources/test_dedup.py possible.
    """
    joined = "|".join(normalize_for_hash(part) for part in parts)
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RawItem:
    """
    One item from an upstream source, already in ``articles`` row shape.

    ``guid`` is the per-source identity key. The RSS path keeps using the feed
    entry's own id (unchanged behaviour); adapters over structured APIs use
    :func:`content_hash`. Either way the ``(feed_id, guid)`` unique constraint
    on ``articles`` is what actually enforces dedup at insert time.
    """

    guid: str
    url: str
    title: str
    description: str = ""
    content: str = ""
    normalized_content: str = ""
    published_date: datetime | None = None
    author: str = ""
    categories: tuple[str, ...] = field(default_factory=tuple)
    language: str = "en"

    def as_article_fields(self) -> dict[str, Any]:
        """
        The ``articles`` column values for this item.

        ``word_count`` is derived rather than stored so it can never disagree
        with ``normalized_content``; the expression matches the RSS normalizer's
        exactly, including the empty-string-means-zero case.
        """
        return {
            "guid": self.guid,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "normalized_content": self.normalized_content,
            "published_date": self.published_date,
            "author": self.author,
            "categories": list(self.categories),
            "word_count": len(self.normalized_content.split()) if self.normalized_content else 0,
            "language": self.language,
        }

    @classmethod
    def from_normalized(cls, data: dict[str, Any]) -> RawItem:
        """
        Build from a ``RSSFetcher.normalize_article()`` dict.

        This is the one place the RSS shape is converted, so
        :class:`~src.sources.rss_adapter.RSSAdapter` cannot drift from the
        fetcher it wraps: an unknown key here is a hard error rather than a
        field quietly dropped on the floor.
        """
        unknown = set(data) - set(ARTICLE_FIELDS)
        if unknown:
            raise ValueError(
                f"normalized article carries field(s) unknown to RawItem: {sorted(unknown)}"
            )
        return cls(
            guid=data.get("guid") or "",
            url=data.get("url") or "",
            title=data.get("title") or "",
            description=data.get("description") or "",
            content=data.get("content") or "",
            normalized_content=data.get("normalized_content") or "",
            published_date=data.get("published_date"),
            author=data.get("author") or "",
            categories=tuple(data.get("categories") or ()),
            language=data.get("language") or "en",
        )


@runtime_checkable
class SourceAdapter(Protocol):
    """
    What every ingestion source must look like.

    ``name``, ``source_url`` and ``category`` are what
    :func:`src.sources.store.ensure_source` writes to the source row, so that a
    non-RSS source is an ordinary row downstream and beat scoping, the sources
    CLI and the citation map all keep working unchanged.
    """

    name: str
    source_url: str
    category: str

    async def fetch(self, since: datetime) -> list[RawItem]:
        """
        Items published at or after ``since``.

        Returns ``[]`` when the upstream is reachable and has nothing new.
        Raises :class:`SourceUnavailable` when it could not be reached or its
        response could not be understood.
        """
        ...
