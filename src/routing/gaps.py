"""
What the corpus is talking about that no watch can see.

**The unrouted count is the coverage-gap signal.** It is the only place a
missing sensor becomes visible *before* a staleness alert fires -- a staleness
alert says a watch has gone quiet, which is also what a watch with a broken
trigger looks like, and neither says "there is a whole subject here you never
registered a watch for". Logging that as a bare integer would make it useless:
"988 unrouted" is not actionable, and nobody reads 988 hashes.

Two layers of grouping, both deterministic, and neither of them a new algorithm:

* **Near-duplicate clusters.** The stored MinHash signature of every unrouted
  observation, grouped by :func:`src.sources.minhash.group_near_duplicates`,
  which is the same grouping the rest of the system uses. A cluster of six is
  one story carried by six outlets and seen by no watch, which is the strongest
  form of the signal: the environment thought it was important and the operator
  has no sensor on it.
* **Gap terms.** Document frequency of salient words across all unrouted
  observations. This catches the case near-duplicate grouping cannot: a subject
  covered by forty *different* stories over a month, no two of them
  near-duplicates. Frequency is counted per observation, not per occurrence, so
  one verbose article cannot invent a theme.

**This module proposes nothing.** Proposing watches from these clusters is
backlog task 021, and it is deliberately not here -- invariant 6 says the system
never authors its own watches, and the way that invariant is lost is one
convenient path at a time. What this produces is a report on disk. A human, or
task 021 under a human, reads it.

Added 2026-08-31 for backlog task 015.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config.settings import settings
from ..database.models import Observation, RSSFeed
from ..sources.minhash import group_near_duplicates
from ..sources.observation import payload_text
from ..utils import utcnow
from .router import RoutingReport
from .salience import gap_terms

__all__ = [
    "GAP_REPORT_SCHEMA",
    "UnroutedCluster",
    "cluster_unrouted",
    "default_gap_report_path",
    "gap_report",
    "gap_terms",
    "write_gap_report",
]

# How many hashes go into one IN (...) clause. Well under SQLite's bound
# parameter ceiling on every version this runs on.
_BATCH = 400

# Bumped whenever the JSON below changes shape, so task 021 can refuse a report
# it does not understand instead of reading a field that moved.
GAP_REPORT_SCHEMA = "insightweaver.routing.gaps/1"


@dataclass(frozen=True)
class UnroutedCluster:
    """
    One group of unrouted observations that are near-duplicates of each other.

    ``terms`` labels the cluster with the words its members share, so the file
    is readable without opening every payload.
    """

    members: tuple[str, ...]
    representative_title: str
    sources: tuple[str, ...]
    terms: tuple[tuple[str, int], ...]
    first_published: str | None
    last_published: str | None

    @property
    def size(self) -> int:
        return len(self.members)

    def as_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "representative_title": self.representative_title,
            "members": list(self.members),
            "sources": list(self.sources),
            "terms": [[term, count] for term, count in self.terms],
            "first_published": self.first_published,
            "last_published": self.last_published,
        }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _load(db: Session, hashes: list[str]) -> dict[str, Any]:
    """
    The stored rows for ``hashes``, keyed by hash, read in bounded batches.

    Chunked because ``IN (...)`` is a bound-parameter per element and SQLite has
    a ceiling on those. A silent truncation at that ceiling would understate the
    coverage gap, which is the one direction this report must never err in.
    """
    loaded: dict[str, Any] = {}
    for start in range(0, len(hashes), _BATCH):
        batch = hashes[start : start + _BATCH]
        rows = db.query(
            Observation.content_hash,
            Observation.source_id,
            Observation.payload,
            Observation.minhash,
            Observation.published_date,
        ).filter(Observation.content_hash.in_(batch))
        loaded.update({row[0]: row for row in rows})
    return loaded


def cluster_unrouted(
    db: Session,
    hashes: list[str],
    *,
    threshold: float | None = None,
    rows: dict[str, Any] | None = None,
) -> list[UnroutedCluster]:
    """
    Group the unrouted observations by near-duplicate similarity, largest first.

    Singletons are included. They are most of the corpus and they are still the
    data: task 021 filters, this function reports. Grouping is pairwise, which
    is quadratic -- the CLI's ``--limit`` is what bounds it, and the bound is
    documented there rather than hidden as a silent truncation here.
    """
    if not hashes:
        return []

    by_hash = _load(db, hashes) if rows is None else rows
    feeds = {row.id: row.name for row in db.query(RSSFeed.id, RSSFeed.name)}

    groups = group_near_duplicates(
        {h: tuple(by_hash[h][3] or ()) for h in by_hash},
        settings.near_duplicate_threshold if threshold is None else threshold,
    )

    clusters: list[UnroutedCluster] = []
    for members in groups:
        titles = [str((by_hash[h][2] or {}).get("title") or "") for h in members]
        dates = sorted(d for d in (by_hash[h][4] for h in members) if d is not None)
        clusters.append(
            UnroutedCluster(
                members=tuple(members),
                representative_title=next((t for t in titles if t), ""),
                sources=tuple(sorted({feeds.get(by_hash[h][1]) or "" for h in members} - {""})),
                terms=tuple(gap_terms(titles, limit=8)),
                first_published=_iso(dates[0]) if dates else None,
                last_published=_iso(dates[-1]) if dates else None,
            )
        )

    return sorted(clusters, key=lambda c: (-c.size, c.members[0]))


def gap_report(
    db: Session,
    report: RoutingReport,
    *,
    threshold: float | None = None,
) -> dict[str, Any]:
    """The whole coverage-gap signal as a JSON-serialisable mapping."""
    rows = _load(db, report.unrouted)
    clusters = cluster_unrouted(db, report.unrouted, threshold=threshold, rows=rows)
    texts = [payload_text(rows[h][2] or {}) for h in report.unrouted if h in rows]

    return {
        "schema": GAP_REPORT_SCHEMA,
        "generated_at": utcnow().isoformat(),
        "observations_considered": report.considered,
        "routed_observations": report.routed_count,
        "unrouted_observations": report.unrouted_count,
        "links": len(report.links),
        "watches": list(report.watch_ids),
        "expired_watches": list(report.expired_watch_ids),
        "per_watch": dict(sorted(report.per_watch.items())),
        "clusters": [cluster.as_dict() for cluster in clusters],
        "gap_terms": [[term, count] for term, count in gap_terms(texts)],
    }


def default_gap_report_path() -> Path:
    """
    Where the coverage-gap report lands when nothing says otherwise.

    ``data/routing/unrouted_clusters.json``. Task 021 reads this path; it is a
    derived report, rewritten on every run, and holds nothing that cannot be
    recomputed from the observations.
    """
    return Path(settings.data_dir) / "routing" / "unrouted_clusters.json"


def write_gap_report(payload: dict[str, Any], path: Path | str | None = None) -> Path:
    """Write the report as indented JSON and return where it went."""
    target = Path(path) if path is not None else default_gap_report_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return target
