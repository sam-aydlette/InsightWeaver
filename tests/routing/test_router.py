"""
Running the predicates over stored observations, and recording what matched.

The properties here are the ones that cost money if they break: what is
considered, what is written, and that writing it twice writes it once.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.database.models import RouteCandidate
from src.routing import persist, route

from .conftest import TODAY, WatchRow

CISA = WatchRow("cisa-advisories", [{"entities": ["CISA"], "terms": ["advisory", "alert"]}])
FEDRAMP = WatchRow("fedramp-conmon", [{"terms": ["FedRAMP"], "entities": ["GSA"]}])


class TestWhatRoutes:
    def test_an_observation_matching_nothing_is_unrouted(self, test_session, observe):
        h = observe("A local school board meeting", "nothing to do with any watch")
        report = route(test_session, today=TODAY, watches=[CISA, FEDRAMP])

        assert report.considered == 1
        assert report.routed_count == 0
        assert report.unrouted == [h]
        assert report.per_watch == {"cisa-advisories": 0, "fedramp-conmon": 0}

    def test_a_matching_observation_is_linked_to_the_watch_that_matched(
        self, test_session, observe
    ):
        observe("CISA issues an advisory", "CISA published an advisory today")
        report = route(test_session, today=TODAY, watches=[CISA, FEDRAMP])

        assert report.routed_count == 1
        assert report.unrouted == []
        assert [(link.watch_id, link.clause_index) for link in report.links] == [
            ("cisa-advisories", 0)
        ]

    def test_one_observation_can_route_to_two_watches(self, test_session, observe):
        observe("CISA advisory names GSA", "CISA published an advisory naming GSA and FedRAMP")
        report = route(test_session, today=TODAY, watches=[CISA, FEDRAMP])

        assert report.routed_count == 1
        assert len(report.links) == 2
        assert report.fan_out == 2.0

    def test_fan_out_is_links_per_observation_not_routed_observations(self, test_session, observe):
        observe("CISA advisory names GSA", "CISA published an advisory naming GSA and FedRAMP")
        observe("A local school board meeting", "nothing relevant")
        report = route(test_session, today=TODAY, watches=[CISA, FEDRAMP])

        assert (report.considered, report.routed_count, len(report.links)) == (2, 1, 2)
        assert report.fan_out == 1.0

    def test_the_source_axis_is_read_from_the_feed_row(self, test_session, observe, feed):
        register = feed("Federal Register", "https://federalregister.gov/rss")
        watch = WatchRow("fr-only", [{"sources": ["Federal Register"], "terms": ["FedRAMP"]}])

        observe("A FedRAMP notice", "text", source=register)
        observe("A FedRAMP story", "text")  # default feed, FedScoop

        report = route(test_session, today=TODAY, watches=[watch])
        assert report.per_watch == {"fr-only": 1}

    def test_limit_considers_only_the_last_n(self, test_session, observe):
        for i in range(5):
            observe(f"item {i}", "nothing relevant")

        assert route(test_session, today=TODAY, watches=[CISA], limit=2).considered == 2
        assert route(test_session, today=TODAY, watches=[CISA]).considered == 5


class TestExpiredWatchesAreNotRouted:
    """
    Volume scales with *live* watches, so an expired one is not one.

    Routing to an expired watch spends the adjudicator's budget on a question
    that stopped mattering. The skip is reported rather than silent: "nothing
    routed" and "every watch expired" must not look the same.
    """

    def test_an_expired_watch_is_skipped_and_named(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")
        expired = WatchRow("old", [{"entities": ["CISA"]}], expires=date(2026, 1, 1))

        report = route(test_session, today=TODAY, watches=[expired, CISA])

        assert report.expired_watch_ids == ("old",)
        assert report.watch_ids == ("cisa-advisories",)
        assert report.per_watch == {"cisa-advisories": 1}

    def test_a_watch_expiring_today_is_still_live(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")
        today_watch = WatchRow("today", [{"entities": ["CISA"]}], expires=TODAY)

        report = route(test_session, today=TODAY, watches=[today_watch])
        assert report.per_watch == {"today": 1}


class TestIdempotency:
    """
    The same observation routed twice produces one link.

    Tier 1 is deterministic, so a second run over an unchanged corpus computes
    the same links. Writing them again would double every watch's candidate
    count and, downstream, adjudicate the same document twice.
    """

    def test_routing_twice_writes_one_row(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")

        first = persist(test_session, route(test_session, today=TODAY, watches=[CISA]))
        second = persist(test_session, route(test_session, today=TODAY, watches=[CISA]))

        assert first == {"inserted": 1, "already_linked": 0}
        assert second == {"inserted": 0, "already_linked": 1}
        assert test_session.query(RouteCandidate).count() == 1

    def test_a_third_run_is_still_a_no_op(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")
        observe("CISA issues another advisory", "a second CISA advisory")

        for _ in range(3):
            persist(test_session, route(test_session, today=TODAY, watches=[CISA]))

        assert test_session.query(RouteCandidate).count() == 2

    def test_the_database_refuses_a_duplicate_written_around_persist(self, test_session, observe):
        """
        The unique constraint, not just the pre-read, is what holds.

        ``persist`` skips what it already sees, which makes the *report* honest.
        Two concurrent routing runs would both pass that check, so the guarantee
        has to live in the schema as well.
        """
        from sqlalchemy.exc import IntegrityError

        h = observe("CISA issues an advisory", "CISA published an advisory today")
        persist(test_session, route(test_session, today=TODAY, watches=[CISA]))

        test_session.add(
            RouteCandidate(observation_hash=h, watch_id="cisa-advisories", clause_index=0)
        )
        with pytest.raises(IntegrityError):
            test_session.flush()
        test_session.rollback()

    def test_a_new_observation_adds_exactly_one_link(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")
        persist(test_session, route(test_session, today=TODAY, watches=[CISA]))

        observe("CISA issues a later advisory", "another CISA advisory, later")
        written = persist(test_session, route(test_session, today=TODAY, watches=[CISA]))

        assert written == {"inserted": 1, "already_linked": 1}
        assert test_session.query(RouteCandidate).count() == 2


class TestRouteWritesNothing:
    """``route`` computes; ``persist`` writes. The dry run is not a mode of the writer."""

    def test_route_alone_leaves_the_table_empty(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")
        report = route(test_session, today=TODAY, watches=[CISA])

        assert len(report.links) == 1
        assert test_session.query(RouteCandidate).count() == 0
