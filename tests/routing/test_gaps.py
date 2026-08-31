"""
The coverage-gap signal: what matched nothing, grouped so it can be read.

The landmine this defends: an unrouted *count* is the only place a missing
sensor is visible before a staleness alert fires, and a bare integer is not a
signal anyone can act on. These tests assert the count is accompanied by
something with a subject attached to it.
"""

from __future__ import annotations

import json

from src.routing import GAP_REPORT_SCHEMA, cluster_unrouted, gap_report, gap_terms, route
from src.routing.gaps import default_gap_report_path, write_gap_report

from .conftest import TODAY, WatchRow

CISA = WatchRow("cisa-advisories", [{"entities": ["CISA"], "terms": ["advisory"]}])

WIRE = (
    "The county board voted on Tuesday to approve the stormwater levy after a "
    "two-hour hearing, with the measure passing four votes to one."
)


class TestGapTerms:
    def test_counts_documents_not_occurrences(self):
        """One verbose article must not be able to invent a theme."""
        assert gap_terms(["levy levy levy levy", "levy hearing"]) == [
            ("levy", 2),
            ("hearing", 1),
        ]

    def test_drops_structural_words_and_short_tokens(self):
        assert gap_terms(["The board said that it was a stormwater levy"]) == [
            ("board", 1),
            ("levy", 1),
            ("stormwater", 1),
        ]

    def test_ties_break_alphabetically_so_the_report_is_deterministic(self):
        assert gap_terms(["levy hearing board"]) == [("board", 1), ("hearing", 1), ("levy", 1)]

    def test_is_case_folded(self):
        assert gap_terms(["Stormwater", "stormwater"]) == [("stormwater", 2)]


class TestClusters:
    def test_near_duplicates_land_in_one_cluster(self, test_session, observe, feed):
        """
        The same wire story from two outlets, seen by no watch, is one gap.

        This is the strongest form of the signal: the environment thought the
        story mattered enough to carry twice and the operator has no sensor on
        it.
        """
        other = feed("Cardinal News", "https://cardinalnews.test/rss")
        observe("County approves stormwater levy", WIRE)
        observe("County approves stormwater levy", WIRE + " Reporting by staff.", source=other)

        report = route(test_session, today=TODAY, watches=[CISA])
        assert report.unrouted_count == 2

        clusters = cluster_unrouted(test_session, report.unrouted)
        assert [c.size for c in clusters] == [2]
        assert clusters[0].representative_title == "County approves stormwater levy"
        assert "stormwater" in dict(clusters[0].terms)
        assert set(clusters[0].sources) == {"FedScoop", "Cardinal News"}

    def test_unrelated_observations_stay_separate(self, test_session, observe):
        observe("County approves stormwater levy", WIRE)
        observe("Ferry service resumes", "The harbour authority restored the summer timetable.")

        report = route(test_session, today=TODAY, watches=[CISA])
        clusters = cluster_unrouted(test_session, report.unrouted)
        assert [c.size for c in clusters] == [1, 1]

    def test_largest_cluster_first(self, test_session, observe, feed):
        second = feed("Cardinal News", "https://cardinalnews.test/rss")
        observe("County approves stormwater levy", WIRE)
        observe("County approves stormwater levy", WIRE + " Reporting by staff.", source=second)
        observe("Ferry service resumes", "The harbour authority restored the summer timetable.")

        report = route(test_session, today=TODAY, watches=[CISA])
        assert [c.size for c in cluster_unrouted(test_session, report.unrouted)] == [2, 1]

    def test_a_routed_observation_is_not_in_any_cluster(self, test_session, observe):
        routed = observe("CISA issues an advisory", "CISA published an advisory today")
        observe("County approves stormwater levy", WIRE)

        report = route(test_session, today=TODAY, watches=[CISA])
        members = {h for c in cluster_unrouted(test_session, report.unrouted) for h in c.members}
        assert routed not in members
        assert len(members) == 1

    def test_no_unrouted_observations_means_no_clusters(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")
        report = route(test_session, today=TODAY, watches=[CISA])
        assert cluster_unrouted(test_session, report.unrouted) == []


class TestTheReportTask021Reads:
    """
    The output is a file with a schema, at a path, holding subjects.

    Task 021 proposes watches from these clusters. It is not written yet, so
    what this task owes it is a stable shape and a stable place -- and the
    schema string so it can refuse a report it does not understand rather than
    read a field that moved.
    """

    def test_the_report_carries_counts_clusters_and_terms(self, test_session, observe):
        observe("CISA issues an advisory", "CISA published an advisory today")
        observe("County approves stormwater levy", WIRE)

        report = route(test_session, today=TODAY, watches=[CISA])
        payload = gap_report(test_session, report)

        assert payload["schema"] == GAP_REPORT_SCHEMA
        assert payload["observations_considered"] == 2
        assert payload["routed_observations"] == 1
        assert payload["unrouted_observations"] == 1
        assert payload["watches"] == ["cisa-advisories"]
        assert payload["per_watch"] == {"cisa-advisories": 1}
        assert len(payload["clusters"]) == 1
        assert "stormwater" in dict(tuple(t) for t in payload["gap_terms"])

    def test_the_unrouted_count_never_travels_without_its_clusters(self, test_session, observe):
        """The whole point. A count with nothing attached is not a signal."""
        observe("County approves stormwater levy", WIRE)
        payload = gap_report(test_session, route(test_session, today=TODAY, watches=[CISA]))

        assert payload["unrouted_observations"] > 0
        assert payload["clusters"]
        assert payload["gap_terms"]

    def test_it_is_written_as_json_where_it_is_asked_for(self, test_session, observe, tmp_path):
        observe("County approves stormwater levy", WIRE)
        payload = gap_report(test_session, route(test_session, today=TODAY, watches=[CISA]))

        target = tmp_path / "nested" / "unrouted.json"
        assert write_gap_report(payload, target) == target
        assert json.loads(target.read_text())["schema"] == GAP_REPORT_SCHEMA

    def test_the_default_path_is_under_the_data_directory(self):
        path = default_gap_report_path()
        assert path.name == "unrouted_clusters.json"
        assert path.parent.name == "routing"
