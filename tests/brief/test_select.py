"""
``select_brief`` against a real database, no rendering: header, MOVED, DUE and
WATCHING. Rows are inserted out of the order the brief must print them, so a
missing sort is a failure, and each threshold is tested on both sides of its
boundary. QUIET is in ``test_select_quiet.py``.

Added 2026-09-23 for backlog task 031; strengthened the same day after review.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from src.brief.select import HORIZON_DAYS, REVIEW_BANNER_DAYS, select_brief
from src.position.position import Decision
from tests.evidence.stubs import add_observations, add_routes, add_watches

from .rows import (
    AS_OF,
    SINCE,
    _belief,
    _evidence,
    _obs,
    _position,
    _select,
    _source,
    _watch,
)


class TestHeader:
    def test_sources_sorted_by_name_with_window_counts_and_the_last_attempt(self, test_session):
        zeta = _source(test_session, "Zeta Feed", datetime(2026, 9, 19, 5, 0))
        alpha = _source(test_session, "Alpha Feed", datetime(2026, 9, 19, 5, 0), "timeout")
        _obs(test_session, "a1", alpha.id, "t1", None, datetime(2026, 9, 15), [1, 2, 3])
        _obs(test_session, "a2", alpha.id, "t2", None, SINCE, [1, 2, 4])  # on the boundary: in
        _obs(test_session, "z1", zeta.id, "t3", None, SINCE - timedelta(seconds=1), [4, 5, 6])

        header = _select(test_session, _position(date(2026, 9, 1))).header

        assert [s.name for s in header.sources] == ["Alpha Feed", "Zeta Feed"]
        alpha_state, zeta_state = header.sources
        assert (alpha_state.items_in_window, alpha_state.last_error) == (2, "timeout")
        assert (zeta_state.items_in_window, zeta_state.last_error) == (0, None)
        assert zeta_state.last_attempt == datetime(2026, 9, 19, 5, 0)

    def test_the_review_banner_turns_on_the_day_after_the_threshold(self, test_session):
        at = _select(test_session, _position(AS_OF.date() - timedelta(days=REVIEW_BANNER_DAYS)))
        past = _select(
            test_session, _position(AS_OF.date() - timedelta(days=REVIEW_BANNER_DAYS + 1))
        )
        assert (at.header.days_since_review, at.header.review_banner) == (REVIEW_BANNER_DAYS, False)
        assert past.header.review_banner is True
        assert REVIEW_BANNER_DAYS == 90  # the number the task file names

    def test_never_reviewed_and_not_read_both_carry_the_banner(self, test_session):
        never = _select(test_session, _position(None))
        assert (never.header.reviewed, never.header.review_banner) == (None, True)

        unread = _select(
            test_session, position=None, position_problem="x is not a Position:\n  - y"
        )
        assert unread.header.position_problem == "x is not a Position:\n  - y"
        assert unread.header.review_banner is True
        assert unread.position_read is False


class TestMoved:
    def test_clusters_and_citations_are_ordered_by_date_before_hash(self, test_session):
        watch = _watch(test_session, "w")
        source = _source(test_session, "Feed")
        # The earlier observation has the LARGER hash in both pairs, so an
        # order by hash alone gets both wrong.
        later_small = _obs(
            test_session, "aa", source.id, "later", None, datetime(2026, 9, 16), [7] * 10
        )
        earlier_big = _obs(
            test_session, "zz", source.id, "earlier", None, datetime(2026, 9, 15), [7] * 10
        )
        single_later = _obs(
            test_session, "ab", source.id, "single", None, datetime(2026, 9, 17), [9] * 10
        )
        for obs in (later_small, single_later, earlier_big):
            _evidence(test_session, obs.content_hash, watch.id, datetime(2026, 9, 18))

        [moved] = _select(test_session).moved

        assert moved.state is None
        assert [c[0].title for c in moved.clusters] == ["earlier", "single"]
        assert [c.title for c in moved.clusters[0]] == ["earlier", "later"]

    def test_two_prompt_versions_are_two_citations_of_one_observation(self, test_session):
        watch = _watch(test_session, "w")
        source = _source(test_session, "Feed")
        obs = _obs(test_session, "a1", source.id, "t", None, datetime(2026, 9, 15), [1] * 10)
        _evidence(test_session, obs.content_hash, watch.id, datetime(2026, 9, 18), "v2")
        _evidence(test_session, obs.content_hash, watch.id, datetime(2026, 9, 18), "v1")

        [moved] = _select(test_session).moved

        assert [(c.content_hash, c.prompt_version) for c in moved.clusters[0]] == [
            (obs.content_hash, "v1"),
            (obs.content_hash, "v2"),
        ]

    def test_only_evidence_created_inside_the_window_moves(self, test_session):
        watch = _watch(test_session, "w")
        source = _source(test_session, "Feed")
        before = _obs(test_session, "b1", source.id, "before", None, datetime(2026, 9, 1), [1] * 10)
        edge = _obs(test_session, "e1", source.id, "edge", None, datetime(2026, 9, 1), [2] * 10)
        after = _obs(test_session, "f1", source.id, "after", None, datetime(2026, 9, 1), [3] * 10)
        _evidence(test_session, before.content_hash, watch.id, SINCE - timedelta(seconds=1))
        _evidence(test_session, edge.content_hash, watch.id, SINCE)
        _evidence(test_session, after.content_hash, watch.id, AS_OF + timedelta(seconds=1))

        [moved] = _select(test_session).moved

        assert [c[0].title for c in moved.clusters] == ["edge"]

    def test_a_watch_that_expired_or_was_resolved_in_the_window_still_shows_its_evidence(
        self, test_session
    ):
        """Grading needs the evidence, so the watch is shown with its state, not dropped."""
        expired = _watch(test_session, "expired", expires=date(2026, 9, 18))
        resolved = _watch(
            test_session,
            "resolved",
            resolved_at=datetime(2026, 9, 19),
            outcome="no",
            resolution_note="n",
        )
        retired = _watch(test_session, "retired", retired_at=datetime(2026, 9, 19))
        source = _source(test_session, "Feed")
        for n, w in enumerate((expired, resolved, retired)):
            obs = _obs(test_session, f"x{n}", source.id, "t", None, datetime(2026, 9, 15), [n] * 10)
            _evidence(test_session, obs.content_hash, w.id, datetime(2026, 9, 17))

        moved = {m.watch_id: m.state for m in _select(test_session).moved}

        assert moved == {
            "expired": "expired 2026-09-18, unresolved",
            "resolved": "resolved no",
            "retired": "retired",
        }


class TestDue:
    def test_decisions_and_watches_inside_the_horizon_sorted_by_date(self, test_session):
        horizon = AS_OF.date() + timedelta(days=HORIZON_DAYS)
        position = _position(
            date(2026, 9, 1),
            Decision(key="edge", name="On the horizon", deadline=horizon),
            Decision(key="past", name="Past due", deadline=date(2026, 9, 10)),
            Decision(key="beyond", name="Beyond", deadline=horizon + timedelta(days=1)),
            Decision(key="soon", name="Soon", deadline=date(2026, 9, 25), stake="medium"),
        )
        _watch(test_session, "within-horizon", expires=date(2026, 9, 30))
        _watch(
            test_session,
            "resolved-soon",
            expires=date(2026, 9, 22),
            resolved_at=datetime(2026, 9, 15),
            outcome="yes",
            resolution_note="settled",
        )
        _watch(test_session, "expired-open", expires=date(2026, 9, 5))

        brief = _select(test_session, position)

        assert [(d.key, d.days_left) for d in brief.due_decisions] == [
            ("past", -10),
            ("soon", 5),
            ("edge", HORIZON_DAYS),
        ]
        assert [(w.watch_id, w.days_left) for w in brief.due_watches] == [
            ("expired-open", -15),
            ("within-horizon", 10),
        ]


class TestWatching:
    def test_one_row_per_live_watch_sorted_by_id_with_the_belief_as_of(self, test_session):
        over = _watch(test_session, "overridden", belief=0.2)
        _watch(test_session, "fallback", belief=0.3, created_at=datetime(2026, 8, 1))
        _watch(test_session, "gone", expires=date(2026, 9, 19))
        _belief(test_session, over.id, 0.9, datetime(2026, 9, 18))
        _belief(test_session, over.id, 0.4, datetime(2026, 9, 1))
        _belief(test_session, over.id, 0.1, AS_OF + timedelta(minutes=1))  # after as_of: not yet
        source = _source(test_session, "Feed")
        obs_in = _obs(test_session, "w1", source.id, "t", None, datetime(2026, 9, 14), [1] * 10)
        obs_out = _obs(test_session, "w2", source.id, "t2", None, datetime(2026, 9, 14), [2] * 10)
        _evidence(test_session, obs_in.content_hash, over.id, datetime(2026, 9, 15))
        _evidence(test_session, obs_out.content_hash, over.id, datetime(2026, 9, 2))

        rows = _select(test_session).watching

        assert [r.watch_id for r in rows] == ["fallback", "overridden"]
        fallback, overridden = rows
        assert (fallback.belief, fallback.belief_source, fallback.belief_date) == (
            0.3,
            "file",
            date(2026, 8, 1),
        )
        assert (overridden.belief, overridden.belief_source, overridden.belief_date) == (
            0.9,
            "principal",
            date(2026, 9, 18),
        )
        assert (overridden.evidence_in_window, overridden.last_evidence) == (1, date(2026, 9, 15))


def test_select_brief_is_deterministic(test_session):
    add_watches(test_session)
    add_observations(test_session)
    add_routes(test_session)
    as_of, since = datetime(2026, 9, 1, 6, 0), datetime(2026, 1, 1, 0, 0)
    assert select_brief(test_session, as_of=as_of, since=since, position=None) == select_brief(
        test_session, as_of=as_of, since=since, position=None
    )
