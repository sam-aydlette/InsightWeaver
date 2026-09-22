"""
The router over a stored corpus: what routes, idempotency, the unrouted report.

The corpus and watches come from tests/evidence/stubs.py, the same fixture the
replay tests use, so routing and replay cannot drift apart about what the
corpus contains. Two of the four items carry a watch's terms; two carry
nothing any watch is written for.
"""

from datetime import date, datetime

import pytest

from src.database.models import Observation, Route, Watch
from src.routing import RoutingReport, live_watches, route
from src.sources.base import RawItem
from src.sources.store import ensure_source, store_items

from ..evidence.stubs import add_observations, add_watches

TODAY = date(2026, 9, 1)
SINCE = datetime(2026, 8, 1)


@pytest.fixture
def corpus(test_session):
    add_watches(test_session)
    add_observations(test_session)
    return test_session


def _routes(session) -> set[tuple[str, str]]:
    return {(r.observation_hash, r.watch_id) for r in session.query(Route).all()}


def _hash_of(session, guid: str) -> str:
    for h, payload in session.query(Observation.content_hash, Observation.payload).all():
        if payload["guid"] == guid:
            return h
    raise AssertionError(guid)


class TestRouting:
    def test_routes_the_items_that_carry_a_trigger_and_nothing_else(self, corpus):
        report = route(corpus, since=SINCE, today=TODAY)

        assert _routes(corpus) == {
            (_hash_of(corpus, "doc-1"), "conmon-scope-expands"),
            (_hash_of(corpus, "doc-2"), "hiring-market-tightens"),
        }
        assert report.observations == 4
        assert report.routed == 2
        assert report.unrouted == 2
        assert report.written is True

    def test_records_the_first_clause_that_fired(self, corpus):
        """A watch whose second clause is the one that matches records index 1."""
        corpus.add(
            Watch(
                id="fruit",
                claim="Fall fruit guidance changes.",
                belief=0.5,
                decision_key="d",
                so_what="because",
                triggers=[{"terms": ["nothing-that-appears"]}, {"terms": ["persimmons"]}],
                expires=date(2027, 1, 1),
                staleness_alert_days=30,
            )
        )
        corpus.flush()

        route(corpus, since=SINCE, today=TODAY)

        rows = corpus.query(Route.watch_id, Route.clause_index).order_by(Route.watch_id).all()
        assert [(w, c) for w, c in rows] == [
            ("conmon-scope-expands", 0),
            ("fruit", 1),
            ("hiring-market-tightens", 0),
        ]

    def test_routing_twice_produces_one_link_per_pair(self, corpus):
        first = route(corpus, since=SINCE, today=TODAY)
        second = route(corpus, since=SINCE, today=TODAY)

        assert corpus.query(Route).count() == 2
        assert [w.new for w in first.watches] == [1, 1]
        assert [w.new for w in second.watches] == [0, 0]
        assert [w.total for w in second.watches] == [1, 1]

    def test_a_dry_run_computes_the_same_report_and_writes_nothing(self, corpus):
        dry = route(corpus, since=SINCE, today=TODAY, write=False)
        assert corpus.query(Route).count() == 0
        assert dry.written is False

        wet = route(corpus, since=SINCE, today=TODAY)
        assert [(w.watch_id, w.new, w.total) for w in dry.watches] == [
            (w.watch_id, w.new, w.total) for w in wet.watches
        ]
        assert (dry.unrouted, dry.unrouted_by_source, dry.clusters, dry.clusters_omitted) == (
            wet.unrouted,
            wet.unrouted_by_source,
            wet.clusters,
            wet.clusters_omitted,
        )

    def test_an_expired_watch_is_not_live(self, corpus):
        assert {w.watch_id for w in live_watches(corpus, date(2027, 1, 1))} == {
            "conmon-scope-expands"
        }
        report = route(corpus, since=SINCE, today=date(2027, 1, 1))
        assert [w.watch_id for w in report.watches] == ["conmon-scope-expands"]

    def test_rebuild_discards_links_and_routes_the_whole_corpus(self, corpus):
        route(corpus, since=SINCE, today=TODAY)
        stale = Route(
            observation_hash=_hash_of(corpus, "doc-3"),
            watch_id="conmon-scope-expands",
            clause_index=0,
        )
        corpus.add(stale)
        corpus.flush()

        report = route(corpus, since=datetime(2030, 1, 1), today=TODAY, rebuild=True)

        assert report.rebuild is True
        assert corpus.query(Route).count() == 2
        assert (_hash_of(corpus, "doc-3"), "conmon-scope-expands") not in _routes(corpus)
        # Routing covered the corpus; the unrouted report covers the window, which is empty.
        assert report.observations == 4
        assert report.unrouted == 0
        assert report.clusters == []

    def test_the_window_excludes_older_items(self, corpus):
        report = route(corpus, since=datetime(2026, 8, 21), today=TODAY)
        # doc-1 was published 2026-08-20 and falls outside the window.
        assert report.observations == 3
        assert (_hash_of(corpus, "doc-1"), "conmon-scope-expands") not in _routes(corpus)

    def test_an_undated_item_falls_back_to_when_it_was_observed(self, corpus):
        source = ensure_source(corpus, "Undated Feed", "https://example.org/undated", "misc")
        store_items(
            corpus,
            source,
            [
                RawItem(
                    guid="u", url="https://example.org/u", title="ConMon news", published_date=None
                )
            ],
        )
        corpus.flush()

        report = route(corpus, since=datetime(2026, 8, 21), today=TODAY)

        assert (_hash_of(corpus, "u"), "conmon-scope-expands") in _routes(corpus)
        assert report.observations == 4


class TestUnroutedReport:
    def test_unrouted_items_are_clustered_and_named_by_source(self, corpus):
        report = route(corpus, since=SINCE, today=TODAY)

        assert report.unrouted == 2
        assert report.unrouted_by_source == [("Example Agency", 2)]
        assert sum(c.size for c in report.clusters) == 2
        assert all(c.sources == ("Example Agency",) for c in report.clusters)
        assert {c.title for c in report.clusters} == {
            "Persimmons ripen after the first frost",
            "Notice of meeting",
        }

    def test_the_listing_is_bounded_and_says_what_it_left_out(self, test_session):
        add_watches(test_session)
        source = ensure_source(test_session, "Bulk", "https://example.org/bulk", "misc")
        items = [
            RawItem(
                guid=f"b{i}",
                url=f"https://example.org/b{i}",
                title=f"Unrelated story number {i} about {i * 7919}",
                normalized_content=f"Body {i} " + " ".join(str(i * k) for k in range(1, 30)),
                published_date=datetime(2026, 8, 20),
            )
            for i in range(14)
        ]
        store_items(test_session, source, items)
        test_session.flush()

        report = route(test_session, since=SINCE, today=TODAY)

        assert report.unrouted == 14
        assert len(report.clusters) == 10
        assert report.clusters_omitted == 4

    def test_clustering_is_skipped_above_the_bound_and_says_so(self, test_session, monkeypatch):
        """The pairwise grouper is O(n^2); the report refuses to run it over a corpus."""
        import importlib

        # The package re-exports the route() function under the same name as the
        # submodule, so fetch the module through importlib rather than by attribute.
        module = importlib.import_module("src.routing.route")
        monkeypatch.setattr(module, "CLUSTER_LIMIT", 3)
        add_observations(test_session)

        report = route(test_session, since=SINCE, today=TODAY)

        assert report.unrouted == 4
        assert report.clustering_skipped == 4
        assert report.clusters == []
        assert report.unrouted_by_source == [("Example Agency", 4)]

    def test_no_live_watches_means_everything_is_unrouted(self, test_session):
        add_observations(test_session)
        report = route(test_session, since=SINCE, today=TODAY)
        assert isinstance(report, RoutingReport)
        assert report.watches == []
        assert report.unrouted == 4
