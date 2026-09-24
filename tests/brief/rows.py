"""
Row builders for the selector tests, shared by ``test_select.py`` and
``test_select_quiet.py``. Every row takes an explicit timestamp; nothing here
reads the wall clock.

Added 2026-09-23 for backlog task 031.
"""

from __future__ import annotations

from datetime import date, datetime

from src.brief.select import select_brief
from src.database.models import (
    Adjudication,
    Evidence,
    Observation,
    Route,
    RSSFeed,
    Watch,
    WatchBelief,
)
from src.position.position import Position

AS_OF = datetime(2026, 9, 20, 6, 0)
SINCE = datetime(2026, 9, 13, 6, 0)


def _add(session, row):
    session.add(row)
    session.flush()
    return row


def _source(session, name, last_fetched=None, last_error=None):
    row = RSSFeed(name=name, url=f"u:{name}", last_fetched=last_fetched, last_error=last_error)
    return _add(session, row)


def _obs(session, suffix, source_id, title, published, observed_at, minhash):
    row = Observation(
        content_hash=f"sha256:{suffix.ljust(64, '0')}",
        source_id=source_id,
        payload={"title": title},
        minhash=minhash,
        published_date=published,
        observed_at=observed_at,
    )
    return _add(session, row)


def _watch(session, watch_id, **overrides):
    fields = {
        "id": watch_id,
        "claim": f"claim for {watch_id}",
        "belief": 0.4,
        "decision_key": "renew-authorization",
        "so_what": "matters",
        "triggers": [{"terms": ["x"]}],
        "expires": date(2027, 1, 1),
        "staleness_alert_days": 14,
    }
    fields.update(overrides)
    return _add(session, Watch(**fields))


def _evidence(session, obs_hash, watch_id, created_at, prompt_version="v1"):
    row = Evidence(
        observation_hash=obs_hash,
        watch_id=watch_id,
        direction="supports",
        magnitude=0.5,
        prompt_version=prompt_version,
        created_at=created_at,
    )
    return _add(session, row)


def _route(session, obs_hash, watch_id, routed_at):
    row = Route(observation_hash=obs_hash, watch_id=watch_id, clause_index=0, routed_at=routed_at)
    return _add(session, row)


def _belief(session, watch_id, belief, observed_at):
    row = WatchBelief(watch_id=watch_id, belief=belief, source="principal", observed_at=observed_at)
    return _add(session, row)


def _adjudication(session, obs_hash, watch_id, created_at, outcome="failed", error=None):
    row = Adjudication(
        observation_hash=obs_hash,
        watch_id=watch_id,
        prompt_version="v1",
        outcome=outcome,
        error=error,
        created_at=created_at,
    )
    return _add(session, row)


def _position(reviewed, *decisions):
    return Position(path=None, version=1, decisions=tuple(decisions), reviewed=reviewed)


def _select(session, position=None, **kw):
    return select_brief(session, as_of=AS_OF, since=SINCE, position=position, **kw)
