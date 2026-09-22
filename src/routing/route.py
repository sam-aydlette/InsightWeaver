"""
The router: evaluate live watches over a window of observations.

Reads ``observations`` (never ``articles``), the source name from the source
row, and ``watches.triggers``. Writes ``routes``. Idempotent: a pair already
linked is not linked again, so running twice produces one link per pair, and a
``--dry-run`` computes the same report without writing.

The unrouted report is the coverage-gap signal, not a footnote. An observation
that routes to nothing is either noise, which is the common case and the point,
or a story no watch is written to catch. The two look identical as a count;
grouped by near-duplicate cluster and named by source, the second kind shows
up as one story carried by several outlets that nothing caught.

Added 2026-09-22 for backlog task 028.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.database.models import Observation, Route, RSSFeed, Watch
from src.position.ledger import live_clause
from src.sources.minhash import group_near_duplicates
from src.sources.observation import observation_text

from .compile import CompiledWatch, compile_triggers

__all__ = ["RoutingReport", "UnroutedCluster", "WatchRouting", "live_watches", "route"]

# How many unrouted clusters the report carries. The count is always complete;
# only the listing is bounded, and the report says how many it left out.
CLUSTERS_SHOWN = 10

# The near-duplicate grouper is pairwise, O(n^2), sized for a day of ingestion
# (src/sources/minhash.py). Above this many unrouted observations the report
# skips clustering and says so, rather than running for hours on a rebuild;
# the per-source counts and the total are still complete.
CLUSTER_LIMIT = 2000


@dataclass(frozen=True)
class WatchRouting:
    watch_id: str
    new: int  # links written (or that would be written) this run
    total: int  # observations in the window that route to this watch


@dataclass(frozen=True)
class UnroutedCluster:
    size: int
    sources: tuple[str, ...]
    title: str
    hashes: tuple[str, ...]


@dataclass
class RoutingReport:
    since: datetime
    rebuild: bool
    observations: int  # rows routed: the window, or the whole corpus on rebuild
    watches: list[WatchRouting] = field(default_factory=list)
    unrouted: int = 0
    unrouted_by_source: list[tuple[str, int]] = field(default_factory=list)
    clusters: list[UnroutedCluster] = field(default_factory=list)
    clusters_omitted: int = 0
    clustering_skipped: int = 0  # unrouted observations left unclustered, over CLUSTER_LIMIT
    written: bool = False

    @property
    def routed(self) -> int:
        return self.observations - self.unrouted


def live_watches(db: Session, today: date) -> list[CompiledWatch]:
    """
    Every watch routing may link to, compiled.

    Live means not expired, not retired and not resolved; the definition is
    :func:`src.position.ledger.live_clause` and this is one of its readers.
    """
    rows = db.query(Watch.id, Watch.triggers).filter(live_clause(today)).order_by(Watch.id)
    return [compile_triggers(str(watch_id), triggers) for watch_id, triggers in rows.all()]


def _window(db: Session, since: datetime | None):
    """Observations in the window, with their source name, in hash order."""
    query = db.query(
        Observation.content_hash,
        Observation.payload,
        Observation.minhash,
        Observation.published_date,
        Observation.observed_at,
        RSSFeed.name,
    ).join(RSSFeed, RSSFeed.id == Observation.source_id)
    if since is not None:
        # published_date can be null for feeds that carry no date; those rows
        # fall back to when we first saw them rather than dropping out.
        query = query.filter(
            or_(
                Observation.published_date >= since,
                and_(Observation.published_date.is_(None), Observation.observed_at >= since),
            )
        )
    return query.order_by(Observation.content_hash).all()


def route(
    db: Session,
    *,
    since: datetime,
    today: date,
    write: bool = True,
    rebuild: bool = False,
) -> RoutingReport:
    """
    Route the window's observations to the live watches.

    ``rebuild`` discards every existing link for the live watches and routes
    the whole corpus, ignoring ``since`` for routing; it is how a changed
    trigger takes effect on observations already stored. Without it, links are
    only added. The unrouted report always describes the window, rebuild or
    not, because that is the period whose coverage gap the operator is reading.
    """
    watches = live_watches(db, today)
    watch_ids = [w.watch_id for w in watches]

    if rebuild and write:
        db.query(Route).filter(Route.watch_id.in_(watch_ids)).delete(synchronize_session=False)
        db.flush()

    rows = _window(db, None if rebuild else since)
    existing: set[tuple[str, str]] = set()
    if watch_ids and not rebuild:
        existing = {
            (str(h), str(w))
            for h, w in db.query(Route.observation_hash, Route.watch_id)
            .filter(Route.watch_id.in_(watch_ids))
            .all()
        }

    new = dict.fromkeys(watch_ids, 0)
    total = dict.fromkeys(watch_ids, 0)
    unrouted: dict[str, tuple[int, ...]] = {}
    details: dict[str, tuple[str, str]] = {}

    for content_hash, payload, minhash, published_date, observed_at, source_name in rows:
        text = observation_text(payload)
        matched = False
        for watch in watches:
            index = watch.first_match(text, str(source_name or ""))
            if index is None:
                continue
            matched = True
            total[watch.watch_id] += 1
            if (content_hash, watch.watch_id) in existing:
                continue
            new[watch.watch_id] += 1
            if write:
                db.add(
                    Route(
                        observation_hash=content_hash,
                        watch_id=watch.watch_id,
                        clause_index=index,
                    )
                )
        if not matched and (published_date or observed_at) >= since:
            unrouted[content_hash] = tuple(minhash)
            details[content_hash] = (str(source_name), str(payload.get("title") or ""))

    if write:
        db.flush()

    report = RoutingReport(
        since=since,
        rebuild=rebuild,
        observations=len(rows),
        watches=[WatchRouting(w, new[w], total[w]) for w in watch_ids],
        unrouted=len(unrouted),
        written=write,
    )
    _cluster(report, unrouted, details)
    return report


def _cluster(
    report: RoutingReport,
    unrouted: dict[str, tuple[int, ...]],
    details: dict[str, tuple[str, str]],
) -> None:
    """Group the unrouted observations by near-duplicate signature, largest first."""
    if not unrouted:
        return
    by_source: dict[str, int] = {}
    for source, _title in details.values():
        by_source[source] = by_source.get(source, 0) + 1
    report.unrouted_by_source = sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(unrouted) > CLUSTER_LIMIT:
        report.clustering_skipped = len(unrouted)
        return
    groups: Sequence[Sequence[str]] = group_near_duplicates(
        unrouted, settings.near_duplicate_threshold
    )
    clusters = []
    for group in groups:
        hashes = tuple(sorted(group))
        sources = tuple(sorted({details[h][0] for h in hashes}))
        clusters.append(
            UnroutedCluster(
                size=len(hashes), sources=sources, title=details[hashes[0]][1], hashes=hashes
            )
        )
    clusters.sort(key=lambda c: (-c.size, c.hashes[0]))
    report.clusters = clusters[:CLUSTERS_SHOWN]
    report.clusters_omitted = max(0, len(clusters) - CLUSTERS_SHOWN)
