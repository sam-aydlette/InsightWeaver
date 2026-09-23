"""
``select_brief``'s QUIET section: staleness on routing recency, silent sources,
pending pairs and failed adjudications.

Added 2026-09-23 for backlog task 031 review.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .rows import (
    AS_OF,
    SINCE,
    _adjudication,
    _evidence,
    _obs,
    _route,
    _select,
    _source,
    _watch,
)


class TestQuiet:
    def test_staleness_is_tested_on_when_routing_last_linked_something(self, test_session):
        """An old item routed yesterday is not silence; a fresh route after as_of is not seen."""
        stale = _watch(test_session, "stale", staleness_alert_days=5)
        _watch(test_session, "never-routed", staleness_alert_days=5)
        backfill = _watch(test_session, "backfill", staleness_alert_days=5)
        future = _watch(test_session, "future-route", staleness_alert_days=5)
        src = _source(test_session, "Feed", datetime(2026, 9, 18))
        old = _obs(
            test_session, "s1", src.id, "o", datetime(2026, 8, 1), datetime(2026, 8, 1), [1] * 10
        )
        _route(test_session, old.content_hash, stale.id, routed_at=datetime(2026, 9, 14))
        _route(test_session, old.content_hash, backfill.id, routed_at=datetime(2026, 9, 19))
        _route(test_session, old.content_hash, future.id, routed_at=AS_OF + timedelta(hours=1))

        quiet = {q.watch_id: q.last_routed for q in _select(test_session).quiet_watches}

        assert quiet == {
            "stale": date(2026, 9, 14),
            "never-routed": None,
            "future-route": None,
        }

    def test_silent_sources_say_whether_they_have_produced_before(self, test_session):
        veteran = _source(test_session, "Veteran", datetime(2026, 9, 18))
        _source(test_session, "Newcomer", datetime(2026, 9, 18))
        _source(test_session, "Broken", datetime(2026, 9, 18), "500")
        _source(test_session, "Not run", SINCE - timedelta(days=1))
        _source(test_session, "Never", None)
        _obs(test_session, "v1", veteran.id, "t", None, datetime(2026, 8, 1), [1] * 10)

        silent = [(s.name, s.produced_before) for s in _select(test_session).silent_sources]

        assert silent == [("Newcomer", False), ("Veteran", True)]

    def test_pending_pairs_and_failed_adjudications(self, test_session):
        w = _watch(test_session, "w")
        closed = _watch(test_session, "closed", retired_at=datetime(2026, 9, 1))
        src = _source(test_session, "Feed")
        obs = [
            _obs(test_session, f"p{n}", src.id, "t", None, datetime(2026, 9, 15), [n] * 10)
            for n in range(4)
        ]
        for o in obs:
            _route(test_session, o.content_hash, w.id, routed_at=datetime(2026, 9, 16))
        _route(test_session, obs[0].content_hash, closed.id, routed_at=datetime(2026, 9, 16))
        _adjudication(test_session, obs[0].content_hash, w.id, datetime(2026, 9, 16), "none")
        _adjudication(test_session, obs[1].content_hash, w.id, datetime(2026, 9, 16), "failed", "x")
        _evidence(
            test_session, obs[2].content_hash, w.id, datetime(2026, 9, 16)
        )  # replay-committed
        _adjudication(
            test_session, obs[3].content_hash, w.id, SINCE - timedelta(days=1), "failed", "old"
        )

        brief = _select(test_session)

        assert [(p.watch_id, p.pairs) for p in brief.pending] == []
        assert [(f.watch_id, f.error) for f in brief.failed] == [("w", "x")]

    def test_a_routed_pair_nobody_has_answered_is_pending(self, test_session):
        w = _watch(test_session, "w")
        src = _source(test_session, "Feed")
        for n in range(2):
            obs = _obs(test_session, f"q{n}", src.id, "t", None, datetime(2026, 9, 15), [n] * 10)
            _route(test_session, obs.content_hash, w.id, routed_at=datetime(2026, 9, 16))

        assert [(p.watch_id, p.pairs) for p in _select(test_session).pending] == [("w", 2)]
