"""
render() on hand-built Brief dataclasses, no database.

Covers the fixed part order, the two flavours' markers, empty-section zeros,
citation formatting including near-duplicate clustering, header variants, DUE
past/expired phrasing, QUIET wording and purity.

Added 2026-09-22 for backlog task 031.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from src.brief.render import render
from src.brief.sections import (
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

AS_OF = datetime(2026, 8, 24, 6, 0)
SINCE = datetime(2026, 8, 17, 6, 0)


def _empty_header(**overrides: Any) -> Header:
    base: dict[str, Any] = {
        "as_of": AS_OF,
        "since": SINCE,
        "position_problem": None,
        "reviewed": date(2026, 8, 1),
        "days_since_review": 23,
        "review_banner": False,
        "sources": (),
    }
    base.update(overrides)
    return Header(**base)


def _empty_brief(**header_overrides) -> Brief:
    return Brief(header=_empty_header(**header_overrides))


def _citation(**overrides: Any) -> Citation:
    base: dict[str, Any] = {
        "content_hash": "sha256:" + "a" * 64,
        "title": "Agency proposes new rule",
        "source": "Federal Register",
        "published": "2026-08-20",
        "direction": "up",
        "magnitude": 0.5,
        "prompt_version": "v1",
    }
    base.update(overrides)
    return Citation(**base)


def _full_brief() -> Brief:
    """A Brief with every section populated, for the purity and flavour checks."""
    sources = (SourceState("feed-a", datetime(2026, 8, 23, 5, 0), None, 3),)
    watching = WatchingRow(
        "w1", "claim", 0.6, "operator", date(2026, 8, 20), "d1", 12, 2, date(2026, 8, 22)
    )
    return Brief(
        header=_empty_header(sources=sources),
        moved=[MovedWatch(watch_id="w1", claim="claim", state=None, clusters=((_citation(),),))],
        due_decisions=[
            DueDecision("d1", "Renew", date(2026, 9, 1), 8, "high"),
        ],
        due_watches=[DueWatch("w2", "watch claim", date(2026, 9, 5), 12)],
        watching=[watching],
        quiet_watches=[QuietWatch("w3", 7, date(2026, 8, 10))],
        silent_sources=[SilentSource("feed-c", True)],
        pending=[PendingWatch("w5", 3)],
        failed=[FailedAdjudication("sha256:" + "d" * 64, "w4", "v1", "parse error")],
    )


@pytest.mark.parametrize(
    "markdown,title_marker,section_markers",
    [
        (False, "BRIEF AS OF", ["MOVED", "DUE", "WATCHING", "QUIET"]),
        (True, "# Brief as of", ["## MOVED", "## DUE", "## WATCHING", "## QUIET"]),
    ],
)
def test_order_and_markers(markdown, title_marker, section_markers):
    text = render(_empty_brief(), markdown=markdown)
    positions = [text.index(m) for m in (title_marker, *section_markers)]
    assert positions == sorted(positions)
    if markdown:
        assert "-" * len("MOVED") not in text
    else:
        assert "MOVED\n" + "-" * len("MOVED") in text
        for line in text.splitlines():
            assert not line.startswith("- ")
            assert not line.startswith("## ")


def test_flavours_differ_only_in_markers():
    def normalize_markdown(text: str) -> list[str]:
        out = []
        for line in text.splitlines():
            if line.startswith("# "):
                out.append(line[2:])
            elif line.startswith("## "):
                out.append(line[3:])
            elif line.startswith("- "):
                out.append("* " + line[2:])
            elif line.startswith("  - "):
                out.append("  * " + line[4:])
            else:
                out.append(line)
        return out

    brief = _full_brief()
    terminal = render(brief, markdown=False)
    md = render(brief, markdown=True)
    # the dashed section underline (terminal only) has no markdown counterpart
    t_lines = [line for line in terminal.splitlines() if not (line and set(line) == {"-"})]
    m_lines = normalize_markdown(md)
    assert len(t_lines) == len(m_lines)
    assert t_lines[0] == m_lines[0].upper()  # title is upper-cased in terminal only
    assert t_lines[1:] == m_lines[1:]


def test_empty_sections_print_zeros():
    text = render(_empty_brief(), markdown=False)
    assert "nothing: no watch gained evidence in the window" in text
    assert "nothing inside the horizon" in text
    assert "no live watches" in text
    assert "watches with nothing routed inside their staleness window: 0" in text
    assert "sources that ran in the window and returned nothing: 0" in text
    assert "routed pairs no adjudication has answered: 0" in text
    assert "failed adjudications in the window: 0" in text


def test_citation_line_fields():
    citation = _citation(
        content_hash="sha256:" + "b" * 64,
        title="Something happened",
        source="Reuters",
        published="2026-08-19",
        direction="down",
        magnitude=1.5,
        prompt_version="v3",
    )
    brief = _empty_brief()
    brief.moved = [
        MovedWatch(watch_id="w1", claim="claim text", state=None, clusters=((citation,),))
    ]
    text = render(brief, markdown=False)
    assert "down 1.50" in text
    assert "2026-08-19" in text
    assert "Reuters: Something happened" in text
    assert "sha256:" + "b" * 12 in text
    assert "v3" in text


@pytest.mark.parametrize(
    "size,expected_also,expected_marker",
    [(3, "(+2 near-duplicates)", 2), (2, "(+1 near-duplicate)", 1)],
)
def test_cluster_near_duplicate_counts(size, expected_also, expected_marker):
    clusters = tuple(
        _citation(content_hash=f"sha256:{n}" + "0" * 63, title=str(n)) for n in range(size)
    )
    brief = _empty_brief()
    brief.moved = [MovedWatch(watch_id="w1", claim="claim", state=None, clusters=(clusters,))]
    text = render(brief, markdown=False)
    assert expected_also in text
    assert text.count("also ") == expected_marker
    if size == 2:
        assert "near-duplicates" not in text  # plural must not appear for a single extra


def test_one_observation_under_two_prompt_versions_is_not_a_near_duplicate_of_itself():
    same = "sha256:" + "e" * 64
    cluster = (
        _citation(content_hash=same, prompt_version="v1"),
        _citation(content_hash=same, prompt_version="v2"),
    )
    brief = _empty_brief()
    brief.moved = [MovedWatch(watch_id="w1", claim="claim", state=None, clusters=(cluster,))]
    text = render(brief, markdown=False)
    assert "near-duplicate" not in text
    assert text.count("also ") == 1  # the second version is still cited


def test_a_watch_that_is_not_live_prints_its_state_beside_its_id():
    brief = _empty_brief()
    brief.moved = [
        MovedWatch("w1", "claim", "expired 2026-08-22, unresolved", ((_citation(),),)),
    ]
    assert "* w1 [expired 2026-08-22, unresolved]: claim" in render(brief, markdown=False)


def test_header_position_problem_never_reviewed_and_banner():
    problem = "position.yaml is not a valid Position:\n  - 'decisions' is required\n  - bad date"
    brief = _empty_brief(position_problem=problem)
    brief.position_read = False
    text = render(brief, markdown=False)
    assert "POSITION NOT READ: position.yaml is not a valid Position:\n" in text
    assert "\n  - 'decisions' is required\n  - bad date\n" in text
    assert "decisions: POSITION NOT READ (see the header)" in text  # DUE says so too
    assert "decisions: POSITION NOT READ" not in render(_empty_brief(), markdown=False)
    text = render(_empty_brief(reviewed=None, days_since_review=None), markdown=False)
    assert "never reviewed" in text
    text_on = render(_empty_brief(review_banner=True), markdown=False)
    text_off = render(_empty_brief(review_banner=False), markdown=False)
    assert "REVIEW OVERDUE" in text_on
    assert "REVIEW OVERDUE" not in text_off


def _three_sources():
    return (
        SourceState(name="feed-a", last_attempt=None, last_error=None, items_in_window=0),
        SourceState(
            name="feed-b",
            last_attempt=datetime(2026, 8, 23, 5, 0),
            last_error="timeout",
            items_in_window=2,
        ),
        SourceState(
            name="feed-c",
            last_attempt=datetime(2026, 8, 22, 4, 0),
            last_error=None,
            items_in_window=1,
        ),
    )


def test_verbose_header_lists_never_fetched_failed_attempt_success_and_none_registered():
    text = render(_empty_brief(sources=_three_sources()), markdown=False, verbose=True)
    assert "* feed-a: never fetched; 0 in window" in text
    # A failed attempt is never printed as a fetch: the stamp is the attempt's.
    assert "* feed-b: LAST ATTEMPT FAILED 2026-08-23 05:00: timeout; 2 in window" in text
    assert "* feed-c: fetched 2026-08-22 04:00; 1 in window" in text
    assert "none registered" in render(_empty_brief(sources=()), markdown=False, verbose=True)


def test_compact_header_is_the_default_and_folds_answered_sources_into_counts():
    """A source that answered, whatever it returned, is a count, never a line.
    A source whose last attempt failed is always a line, every time -- that
    is the one thing invariant 5 requires this header to never hide."""
    text = render(_empty_brief(sources=_three_sources()), markdown=False)
    assert "sources: 3 configured, 1 fetched, 1 failed, 1 never fetched" in text
    assert "* feed-b: LAST ATTEMPT FAILED 2026-08-23 05:00: timeout; 2 in window" in text
    assert "feed-a" not in text  # never-fetched: folded into the count, not named
    assert "feed-c" not in text  # answered cleanly: folded into the count, not named
    assert "none registered" in render(_empty_brief(sources=()), markdown=False)


def test_compact_header_with_no_failures_prints_no_source_bullets():
    sources = (SourceState("feed-a", datetime(2026, 8, 23, 5, 0), None, 3),)
    text = render(_empty_brief(sources=sources), markdown=False)
    assert "sources: 1 configured, 1 fetched, 0 failed, 0 never fetched" in text
    assert "* feed-a" not in text


def test_due_decision_past_and_watch_expired():
    brief = _empty_brief()
    brief.due_decisions = [
        DueDecision(
            key="dec1", name="Renew contract", deadline=date(2026, 8, 1), days_left=-5, stake=None
        )
    ]
    brief.due_watches = [
        DueWatch(watch_id="w1", claim="claim text", expires=date(2026, 8, 1), days_left=-3)
    ]
    text = render(brief, markdown=False)
    assert "5 days PAST" in text
    assert "EXPIRED 2026-08-01, 3 days ago, unresolved" in text


def test_quiet_never_routed_since_date_and_failed_line():
    brief = _empty_brief()
    brief.quiet_watches = [
        QuietWatch(watch_id="w1", staleness_alert_days=7, last_routed=None),
        QuietWatch(watch_id="w2", staleness_alert_days=7, last_routed=date(2026, 8, 10)),
    ]
    brief.failed = [
        FailedAdjudication(
            content_hash="sha256:" + "c" * 64,
            watch_id="w9",
            prompt_version="v2",
            error="model timeout",
        )
    ]
    brief.silent_sources = [SilentSource("feed-c", True), SilentSource("feed-d", False)]
    brief.pending = [PendingWatch("w7", 4), PendingWatch("w8", 1)]
    text = render(brief, markdown=False)
    assert "w1: never routed" in text
    assert "w2: nothing routed since 2026-08-10" in text
    assert "sources that ran in the window and returned nothing: 2" in text
    assert "* feed-c (HAS PRODUCED BEFORE; check the source)" in text
    assert "* feed-d (never produced)" in text
    assert "routed pairs no adjudication has answered: 5" in text
    assert "* w7: 4" in text and "* w8: 1" in text
    assert "sha256:" + "c" * 12 + " / w9 [v2]: model timeout" in text


def test_render_is_pure_and_ends_with_one_newline():
    brief = _full_brief()
    text = render(brief, markdown=False)
    assert text == render(brief, markdown=False)
    assert render(brief, markdown=True) == render(brief, markdown=True)
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
