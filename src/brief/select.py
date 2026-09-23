"""
The brief's sections as data, selected from the database and the Position.

Pure in ``(db, as_of, since, position)``: no wall-clock read, no unordered
iteration, every list sorted by a total key, every query bounded by ``as_of``.
:mod:`src.brief.sections` documents each section's fields; the rules that
need stating live beside the code that applies them:

* MOVED shows every watch with evidence in the window, live or not, labelled
  with its state, because grading an expired watch needs that evidence.
* QUIET's staleness is tested on when routing last linked something, not on
  the item's publication date; a backfilled document routed yesterday is not
  silence. Pending pairs are routed pairs no prompt version has answered.
* The header's source line carries the last attempt, and the render labels a
  failed attempt as one; the row keeps no separate time of the last success.

Added 2026-09-22 for backlog task 031; reworked 2026-09-23 after its review.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import exists, func
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..database.models import Adjudication, Evidence, Observation, Route, RSSFeed, Watch
from ..position.ledger import current_beliefs, live_clause, open_clause
from ..position.position import Position
from ..sources.minhash import group_near_duplicates
from .sections import (
    Brief,
    Citation,
    DueDecision,
    DueWatch,
    FailedAdjudication,
    Header,
    MovedWatch,
    PendingWatch,
    QuietWatch,
    SilentSource,
    SourceState,
    WatchingRow,
)

__all__ = ["HORIZON_DAYS", "REVIEW_BANNER_DAYS", "Brief", "select_brief", "watch_state"]

# Past this many days since the Position was reviewed, every brief carries a
# banner: visible degradation, never suppression. A Position never reviewed,
# or not read at all, carries it from the first brief.
REVIEW_BANNER_DAYS = 90

# DUE looks this far ahead. Chosen 2026-09-22; neither the task file nor
# docs/PLAN.md gives a number ("inside the horizon", "the window ahead"), so
# this is the one setting in the brief that is an assumption. Change it here.
HORIZON_DAYS = 30


def _observed(obs: Any) -> datetime:
    """When an observation happened: published if known, else when it was seen."""
    return obs.published_date or obs.observed_at


def _by_key(rows: Any) -> dict[Any, Any]:
    """A two-column result as a dict; untyped because the models use pre-2.0 ``Column()``."""
    return {row[0]: row[1] for row in rows}


def watch_state(w: Any, today: date) -> str | None:
    """None while live; otherwise the one phrase the brief prints beside the watch."""
    if w.retired_at is not None:
        return "retired"
    if w.resolved_at is not None:
        return f"resolved {w.outcome}"
    if w.expires < today:
        return f"expired {w.expires.isoformat()}, unresolved"
    return None


def _header(
    db: Session, as_of: datetime, since: datetime, position: Position | None, problem: str | None
) -> Header:
    counts = _by_key(
        db.query(Observation.source_id, func.count(Observation.content_hash))
        .filter(Observation.observed_at >= since, Observation.observed_at <= as_of)
        .group_by(Observation.source_id)
        .all()
    )
    sources = tuple(
        SourceState(
            name=str(f.name),
            last_attempt=f.last_fetched,  # type: ignore[arg-type]
            last_error=f.last_error,  # type: ignore[arg-type]
            items_in_window=int(counts.get(f.id, 0)),
        )
        for f in db.query(RSSFeed).order_by(RSSFeed.name, RSSFeed.id).all()
    )
    reviewed = position.reviewed if position is not None else None
    days = (as_of.date() - reviewed).days if reviewed is not None else None
    return Header(
        as_of=as_of,
        since=since,
        position_problem=problem,
        reviewed=reviewed,
        days_since_review=days,
        review_banner=days is None or days > REVIEW_BANNER_DAYS,
        sources=sources,
    )


def _moved(db: Session, since: datetime, as_of: datetime, today: date) -> list[MovedWatch]:
    rows = (
        db.query(Evidence, Observation, RSSFeed.name, Watch)
        .join(Observation, Observation.content_hash == Evidence.observation_hash)
        .join(RSSFeed, RSSFeed.id == Observation.source_id)
        .join(Watch, Watch.id == Evidence.watch_id)
        .filter(Evidence.created_at >= since, Evidence.created_at <= as_of)
        .order_by(Evidence.watch_id, Observation.content_hash, Evidence.prompt_version)
        .all()
    )
    by_watch: dict[str, list[tuple[Any, Any, str]]] = {}
    watches: dict[str, Any] = {}
    for evidence, obs, source_name, watch in rows:
        watch_id = str(evidence.watch_id)
        watches[watch_id] = watch
        by_watch.setdefault(watch_id, []).append((evidence, obs, str(source_name)))

    moved: list[MovedWatch] = []
    for watch_id in sorted(by_watch):
        entries = by_watch[watch_id]
        signatures = {str(obs.content_hash): tuple(obs.minhash) for _e, obs, _s in entries}
        clusters: list[tuple[Citation, ...]] = []
        for group in group_near_duplicates(signatures, settings.near_duplicate_threshold):
            in_group = [(e, o, s) for e, o, s in entries if str(o.content_hash) in group]
            in_group.sort(
                key=lambda t: (_observed(t[1]), str(t[1].content_hash), str(t[0].prompt_version))
            )
            clusters.append(
                tuple(
                    Citation(
                        content_hash=str(obs.content_hash),
                        title=str(obs.payload.get("title") or "(untitled)"),
                        source=source,
                        published=_observed(obs).date().isoformat(),
                        direction=str(evidence.direction),
                        magnitude=float(evidence.magnitude),
                        prompt_version=str(evidence.prompt_version),
                    )
                    for evidence, obs, source in in_group
                )
            )
        clusters.sort(key=lambda c: (c[0].published, c[0].content_hash))
        w = watches[watch_id]
        moved.append(MovedWatch(watch_id, str(w.claim), watch_state(w, today), tuple(clusters)))
    return moved


def _due(position: Position | None, db: Session, today: date, horizon: date) -> tuple[list, list]:
    decisions = (
        sorted(
            (
                DueDecision(d.key, d.name, d.deadline, (d.deadline - today).days, d.stake)
                for d in position.decisions
                if d.deadline <= horizon
            ),
            key=lambda d: (d.deadline, d.key),
        )
        if position is not None
        else []
    )
    watches = sorted(
        (
            DueWatch(str(w.id), str(w.claim), w.expires, (w.expires - today).days)  # type: ignore[arg-type]
            for w in db.query(Watch).filter(open_clause()).all()
            if w.expires <= horizon
        ),
        key=lambda d: (d.expires, d.watch_id),
    )
    return decisions, watches


def _pending(db: Session) -> list[PendingWatch]:
    """Routed pairs on open watches that no prompt version has answered."""
    answered = exists().where(
        Adjudication.observation_hash == Route.observation_hash,
        Adjudication.watch_id == Route.watch_id,
    )
    with_evidence = exists().where(
        Evidence.observation_hash == Route.observation_hash, Evidence.watch_id == Route.watch_id
    )
    rows = (
        db.query(Route.watch_id, func.count(Route.id))
        .join(Watch, Watch.id == Route.watch_id)
        .filter(open_clause(), ~answered, ~with_evidence)
        .group_by(Route.watch_id)
        .order_by(Route.watch_id)
        .all()
    )
    return [PendingWatch(str(watch_id), int(count)) for watch_id, count in rows]


def select_brief(
    db: Session,
    *,
    as_of: datetime,
    since: datetime,
    position: Position | None,
    position_problem: str | None = None,
    horizon_days: int = HORIZON_DAYS,
) -> Brief:
    """Every section, as data. Pure in ``(db, as_of, since, position)``."""
    today = as_of.date()
    horizon = today + timedelta(days=horizon_days)
    live = {str(w.id): w for w in db.query(Watch).filter(live_clause(today)).order_by(Watch.id)}
    beliefs = current_beliefs(db, as_of=as_of)

    brief = Brief(
        header=_header(db, as_of, since, position, position_problem),
        position_read=position is not None,
    )
    brief.moved = _moved(db, since, as_of, today)
    brief.due_decisions, brief.due_watches = _due(position, db, today, horizon)

    evidence_in_window = _by_key(
        db.query(Evidence.watch_id, func.count(Evidence.id))
        .filter(Evidence.created_at >= since, Evidence.created_at <= as_of)
        .group_by(Evidence.watch_id)
        .all()
    )
    last_evidence = _by_key(
        db.query(Evidence.watch_id, func.max(Evidence.created_at))
        .filter(Evidence.created_at <= as_of)
        .group_by(Evidence.watch_id)
        .all()
    )
    last_routed = _by_key(
        db.query(Route.watch_id, func.max(Route.routed_at))
        .filter(Route.routed_at <= as_of)
        .group_by(Route.watch_id)
        .all()
    )
    for watch_id, w in live.items():
        belief = beliefs[watch_id]
        latest = last_evidence.get(watch_id)
        brief.watching.append(
            WatchingRow(
                watch_id=watch_id,
                claim=str(w.claim),
                belief=belief.belief,
                belief_source=belief.source,
                belief_date=belief.observed_at.date(),
                decision_key=str(w.decision_key),
                days_to_expiry=(w.expires - today).days,
                evidence_in_window=int(evidence_in_window.get(watch_id, 0)),
                last_evidence=latest.date() if latest is not None else None,
            )
        )
        routed = last_routed.get(watch_id)
        if routed is None or routed < as_of - timedelta(days=int(w.staleness_alert_days)):
            brief.quiet_watches.append(
                QuietWatch(watch_id, int(w.staleness_alert_days), routed.date() if routed else None)
            )

    ever_produced = {
        int(source_id)
        for (source_id,) in db.query(Observation.source_id)
        .filter(Observation.observed_at <= as_of)
        .distinct()
    }
    ids = _by_key(db.query(RSSFeed.name, RSSFeed.id).all())
    brief.silent_sources = [
        SilentSource(s.name, ids[s.name] in ever_produced)
        for s in brief.header.sources
        if s.last_attempt is not None
        and since <= s.last_attempt <= as_of
        and s.last_error is None
        and s.items_in_window == 0
    ]
    brief.pending = _pending(db)
    brief.failed = [
        FailedAdjudication(
            str(a.observation_hash), str(a.watch_id), str(a.prompt_version), str(a.error or "")
        )
        for a in db.query(Adjudication)
        .filter(Adjudication.outcome == "failed")
        .filter(Adjudication.created_at >= since, Adjudication.created_at <= as_of)
        .order_by(Adjudication.observation_hash, Adjudication.watch_id, Adjudication.prompt_version)
        .all()
    ]
    return brief
