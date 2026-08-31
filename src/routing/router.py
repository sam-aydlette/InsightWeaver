"""
Running the compiled predicates over stored observations, and recording what matched.

Two functions and a hard line between them, on the same pattern as replay:
:func:`route` computes and writes nothing, :func:`persist` writes. The dry run
is not a special mode of the write path -- it *is* the computation, and the
write path is a separate call that takes its result. A reporting mode that
shares a code path with the writer is a reporting mode that eventually writes.

**Reading order is fixed.** Observations are considered newest-first by
``observed_at`` with ``content_hash`` breaking ties, so "the last N
observations" is a deterministic set and not a query plan. Watches are compiled
in id order.

**Expired watches are not routed.** The architectural claim is that volume
scales with *live* watches; a watch whose ``expires`` has passed is not live,
and routing to it would spend the adjudicator's budget on a question that
stopped mattering. The count of skipped watches is reported rather than
swallowed, because "nothing routed today" and "every watch expired last week"
must not look the same.

**This tier reads ``observations`` and never ``articles``.** The 55,249
pre-rewrite rows are the legacy archive; the rule is written in
``src/database/models.py``. There is no import of ``Article`` in this package,
and tests/routing/test_no_model.py asserts it.

Added 2026-08-31 for backlog task 015.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from ..database.models import Observation, RouteCandidate, RSSFeed, Watch
from ..sources.observation import payload_text
from .predicate import CompiledWatch, compile_watches, source_keys

logger = logging.getLogger(__name__)

__all__ = [
    "RoutedLink",
    "RoutingReport",
    "persist",
    "route",
]


@dataclass(frozen=True, order=True)
class RoutedLink:
    """One observation selected as candidate evidence for one watch."""

    observation_hash: str
    watch_id: str
    clause_index: int


@dataclass
class RoutingReport:
    """
    What routing would do. Produced by :func:`route`, which writes nothing.

    ``unrouted`` carries hashes rather than a count, because the count alone is
    useless: it says a gap exists and nothing about where. Clustering them is
    :mod:`src.routing.gaps`.
    """

    considered: int = 0
    watch_ids: tuple[str, ...] = ()
    expired_watch_ids: tuple[str, ...] = ()
    links: list[RoutedLink] = field(default_factory=list)
    unrouted: list[str] = field(default_factory=list)
    per_watch: dict[str, int] = field(default_factory=dict)
    per_clause: dict[tuple[str, int], int] = field(default_factory=dict)

    @property
    def routed_count(self) -> int:
        """Observations with at least one link. Not the number of links."""
        return len({link.observation_hash for link in self.links})

    @property
    def unrouted_count(self) -> int:
        return len(self.unrouted)

    @property
    def fan_out(self) -> float:
        """
        Links per observation considered -- what the adjudicator actually pays for.

        One observation routed to three watches is three adjudications. This is
        the number the ceiling test pins, alongside the routed-observation
        count, because they diverge exactly when a term is added to several
        watches at once.
        """
        return len(self.links) / self.considered if self.considered else 0.0


def _source_lookup(db: Session) -> dict[int, tuple[str | None, str | None]]:
    """``{feed id: (name, url)}`` for every feed, read once rather than per observation."""
    return {row.id: (row.name, row.url) for row in db.query(RSSFeed.id, RSSFeed.name, RSSFeed.url)}


def route(
    db: Session,
    *,
    limit: int | None = None,
    today: date | None = None,
    watches: Sequence[Any] | None = None,
) -> RoutingReport:
    """
    Offer the last ``limit`` observations to every live watch. Writes nothing.

    ``watches`` overrides the stored watch set, which is what the ceiling test
    uses to hold the watch side fixed. ``today`` decides which watches count as
    live; it defaults to the real date, and tests pass their own so the suite
    does not expire.
    """
    stamp = today or date.today()
    rows = list(watches) if watches is not None else db.query(Watch).all()

    live: list[Any] = []
    expired: list[Any] = []
    for row in rows:
        (live if row.expires is None or row.expires >= stamp else expired).append(row)
    compiled: list[CompiledWatch] = compile_watches(live)

    report = RoutingReport(
        watch_ids=tuple(watch.watch_id for watch in compiled),
        expired_watch_ids=tuple(sorted(row.id for row in expired)),
        per_watch={watch.watch_id: 0 for watch in compiled},
    )

    feeds = _source_lookup(db)

    query = db.query(Observation.content_hash, Observation.source_id, Observation.payload).order_by(
        Observation.observed_at.desc(), Observation.content_hash
    )
    if limit is not None:
        query = query.limit(limit)

    for content_hash, source_id, payload in query:
        report.considered += 1
        text = payload_text(payload or {})
        name, url = feeds.get(source_id, (None, None))
        sources = source_keys(name, url, (payload or {}).get("source_url"))

        matched = False
        for watch in compiled:
            index = watch.matching_clause(text, sources)
            if index is None:
                continue
            matched = True
            report.links.append(RoutedLink(content_hash, watch.watch_id, index))
            report.per_watch[watch.watch_id] += 1
            key = (watch.watch_id, index)
            report.per_clause[key] = report.per_clause.get(key, 0) + 1
        if not matched:
            report.unrouted.append(content_hash)

    report.links.sort()
    return report


def persist(db: Session, report: RoutingReport) -> dict[str, int]:
    """
    Write ``report``'s links as :class:`RouteCandidate` rows. Idempotent.

    Returns ``{"inserted": n, "already_linked": m}``. Re-running routing over an
    unchanged corpus inserts nothing: Tier 1 is deterministic, so the second run
    produces the same links, and every one of them is already there.

    The pre-read is what makes the *report* honest -- it is how the caller is
    told nothing was inserted. The database's unique constraint is what makes
    the *table* honest, and it is not removable: two concurrent routing runs
    would both pass this check.
    """
    existing = {
        (row.observation_hash, row.watch_id)
        for row in db.query(RouteCandidate.observation_hash, RouteCandidate.watch_id)
    }

    inserted = 0
    for link in report.links:
        if (link.observation_hash, link.watch_id) in existing:
            continue
        db.add(
            RouteCandidate(
                observation_hash=link.observation_hash,
                watch_id=link.watch_id,
                clause_index=link.clause_index,
            )
        )
        existing.add((link.observation_hash, link.watch_id))
        inserted += 1

    db.flush()
    return {"inserted": inserted, "already_linked": len(report.links) - inserted}
