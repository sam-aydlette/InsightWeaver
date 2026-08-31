"""
The one path by which an adapter's output becomes a stored Observation.

Every adapter in ``src/sources/`` reaches the database through
``src.sources.store.store_items``, and ``store_items`` reaches ``observations``
through :func:`store_observation` here. There is deliberately no second
constructor, no bulk-insert shortcut and no "just this once" path -- the
guarantee that observations are content-addressed is only as strong as the
number of places that can write one.
tests/sources/test_observation.py::TestOneWritePath asserts that count against
the source tree rather than against anyone's intention.

**What is hashed, and why the list is closed.**
:data:`OBSERVATION_FIELDS` is ``ARTICLE_FIELDS`` (which
tests/sources/test_base.py already pins to the live RSS normalizer) minus
``word_count``, plus ``source_url``. Everything in the payload is hashed and
nothing outside the payload is:

* ``word_count`` is dropped because it is derived from ``normalized_content``.
  Storing it would put a second copy of one fact in an immutable row.
* ``source_url`` is added because the same text published by two sources is two
  observations. Who published it is part of what was observed. Grouping the
  pair back together is :mod:`src.sources.minhash`'s job, not the hash's.
* Nothing per-fetch is in the list. This is the landmine the task named: a fetch
  timestamp or a session id inside the hashed payload stores the same document
  on every run, and the symptom looks like broken dedup rather than a broken
  hash. ``observed_at`` is a column on the row and is not in the payload;
  ``RSSFetcher.normalize_article`` leaves ``published_date`` as ``None`` when
  the feed gives no date rather than defaulting it to now, which was checked
  before this list was written (2026-08-31).

The hash itself is :func:`src.sources.base.content_hash`, the function task 005
already introduced. There is one hashing scheme in this repository.

Added 2026-08-31 for backlog task 014.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..config.settings import settings
from ..database.models import Observation, RSSFeed
from .base import ARTICLE_FIELDS, RawItem, content_hash
from .minhash import group_near_duplicates, signature

logger = logging.getLogger(__name__)

__all__ = [
    "OBSERVATION_FIELDS",
    "ObservationRecord",
    "near_duplicate_groups",
    "observation_hash",
    "observation_payload",
    "observe",
    "payload_text",
    "store_observation",
]

# The closed set of payload keys, in hash order. See the module docstring.
OBSERVATION_FIELDS: tuple[str, ...] = ("source_url",) + tuple(
    field for field in ARTICLE_FIELDS if field != "word_count"
)


def _render(value: Any) -> str:
    """One payload value as the string that goes into the hash."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return " ".join(_render(item) for item in value)
    return str(value)


def observation_payload(source_url: str, item: RawItem) -> dict[str, Any]:
    """
    The normalized adapter output for ``item``, verbatim, as stored.

    ``published_date`` is rendered as an ISO string so that the payload is JSON
    round-trippable: a payload that only survives as Python objects is not a raw
    payload retained verbatim, it is a payload retained until the next reader.
    """
    fields = item.as_article_fields()
    fields["source_url"] = source_url
    payload = {key: fields[key] for key in OBSERVATION_FIELDS}
    published = payload.get("published_date")
    payload["published_date"] = published.isoformat() if published is not None else None
    return payload


def observation_hash(payload: dict[str, Any]) -> str:
    """
    The content hash of a payload. A pure function of the payload's values.

    Raises on a payload whose keys are not exactly :data:`OBSERVATION_FIELDS`:
    an extra key would be stored but unhashed, which is the quiet way a
    content-addressed store stops being content-addressed.
    """
    if set(payload) != set(OBSERVATION_FIELDS):
        missing = sorted(set(OBSERVATION_FIELDS) - set(payload))
        extra = sorted(set(payload) - set(OBSERVATION_FIELDS))
        raise ValueError(
            f"observation payload does not match OBSERVATION_FIELDS "
            f"(missing: {missing}, unexpected: {extra}); every stored key must be hashed"
        )
    return content_hash(*(_render(payload[key]) for key in OBSERVATION_FIELDS))


def payload_text(payload: dict[str, Any]) -> str:
    """
    The readable text of a stored observation: title plus body.

    ``normalized_content`` is preferred over ``description`` because it is the
    HTML-stripped full text; ``description`` is the fallback for feeds that
    carry only a summary. Raw ``content`` is never used -- it still carries
    markup, and a word-boundary matcher pointed at markup matches attribute
    values.

    Every deterministic reader of an observation reads *this*. Near-duplicate
    signatures did first; Tier 1 routing joined on 2026-08-31 (backlog task
    015). Two definitions of "the text of an observation" would let a
    near-duplicate group and a routing decision disagree about what a document
    says.
    """
    body = payload.get("normalized_content") or payload.get("description") or ""
    return f"{payload.get('title') or ''} {body}".strip()


def minhash_text(payload: dict[str, Any]) -> str:
    """The text a near-duplicate signature is computed over. See :func:`payload_text`."""
    return payload_text(payload)


@dataclass(frozen=True)
class ObservationRecord:
    """A hashed, signed observation, not yet stored."""

    content_hash: str
    payload: dict[str, Any]
    minhash: tuple[int, ...]
    published_date: datetime | None


def observe(source_url: str, item: RawItem) -> ObservationRecord:
    """Normalize, hash and sign one adapter item. Touches no database."""
    payload = observation_payload(source_url, item)
    return ObservationRecord(
        content_hash=observation_hash(payload),
        payload=payload,
        minhash=signature(minhash_text(payload)),
        published_date=item.published_date,
    )


def store_observation(
    db: Session,
    source: RSSFeed,
    item: RawItem,
    article_id: int | None = None,
) -> tuple[str, bool]:
    """
    Store one observation if it is not already stored. Returns ``(hash, created)``.

    Re-seeing content we already hold is a no-op, not an update and not an
    error: that is what content-addressing buys, and it is why re-running an
    adapter over an unchanged upstream costs one request and zero writes.

    Note what this function cannot do. There is no argument by which a caller
    supplies a hash, so the stored hash is always the hash of the stored payload;
    and if the row exists it returns without touching it, so this path cannot be
    the one that mutates an observation. Attempting it anyway raises
    :class:`~src.database.models.ObservationIsImmutable`.
    """
    record = observe(str(source.url), item)

    existing = (
        db.query(Observation.content_hash)
        .filter(Observation.content_hash == record.content_hash)
        .first()
    )
    if existing is not None:
        return record.content_hash, False

    db.add(
        Observation(
            content_hash=record.content_hash,
            source_id=source.id,
            article_id=article_id,
            payload=record.payload,
            minhash=list(record.minhash),
            published_date=record.published_date,
        )
    )
    db.flush()
    return record.content_hash, True


def near_duplicate_groups(
    db: Session,
    since: datetime | None = None,
    threshold: float | None = None,
) -> list[list[str]]:
    """
    Group stored observations that differ only in boilerplate.

    ``threshold`` defaults to ``settings.near_duplicate_threshold``, which is
    the configured value and the one thing about the grouping that is meant to
    be tuned -- see ``src/sources/minhash.py`` on why the signature parameters
    are not.

    Returns groups of content hashes, singletons included, in a deterministic
    order.
    """
    query = db.query(Observation.content_hash, Observation.minhash)
    if since is not None:
        query = query.filter(Observation.published_date >= since)
    signatures = {row[0]: tuple(row[1] or ()) for row in query.all()}
    return group_near_duplicates(
        signatures,
        settings.near_duplicate_threshold if threshold is None else threshold,
    )
