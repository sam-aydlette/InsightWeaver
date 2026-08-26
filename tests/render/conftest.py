"""
Fixtures for the renderer tests.

Every fixture here is a plain in-memory ``BriefDocument``. Nothing in this
package touches the pipeline, the database, the network or Claude: rendering
is a pure function of a document, and these tests are what pins that down.
"""

from typing import Any

import pytest

from src.render.document import BriefDocument

# Annotated because the renderers take an untyped synthesis payload: without
# it mypy infers a narrow value type from the literal and rejects reusing the
# fixture to build a variant (added 2026-08-26).
SYNTHESIS_DATA: dict[str, Any] = {
    "situations": [
        {
            "title": "Procurement rule change lands^[1]",
            "narrative": "First paragraph with a citation^[1].\n\nSecond paragraph^[2].",
            "actors": [
                {
                    "name": "Agency CIO",
                    "role": "Signs the waiver",
                    "interests": "Keeping the schedule",
                    "epistemic_status": "reported_fact",
                },
                {"name": "Vendor consortium", "role": "Files the protest"},
            ],
            "power_dynamics": {
                "who_benefits": "Incumbent vendors^[1]",
                "who_is_harmed": "New entrants",
                "who_decides": "The contracting officer",
            },
            "coverage_frame": {
                "narrative_layers": "Efficiency framing versus accountability framing",
                "fractures": "Whether speed trades against oversight",
                "bridges": "Both accept the deadline as fixed",
                "structural_absences": "Nobody quotes a program officer",
                "assumed_premise": "That the deadline cannot move",
            },
            "where_this_goes": {
                "branching_paths": "Either the waiver holds^[1] or the protest succeeds",
                "unresolved_questions": {
                    "primary": {
                        "text": "Will the protest be sustained?",
                        "question_id": 7,
                        "appearance_count": 3,
                        "first_asked_at": "2026-01-04T09:00:00",
                    },
                    "secondary": [
                        {"text": "Who audits the waiver?", "question_id": 9, "appearance_count": 1},
                        "A bare legacy string question",
                    ],
                },
                "what_to_watch": [
                    {
                        "observable": "GAO docket entry",
                        "trigger_condition": "filed within 10 days",
                    },
                    "A bare observable",
                ],
            },
            "information_gaps": [
                {
                    "what_is_missing": "The waiver text itself",
                    "why_it_matters": "It defines the exception",
                    "why_missing": "Not published",
                    "feed_recommendation": "Agency press office feed",
                }
            ],
        },
        {
            "title": "A second situation with no optional blocks",
            "narrative": "Short narrative.",
        },
    ],
    "thin_coverage": [
        {
            "title": "Single-article topic",
            "article_count": 1,
            "sources": ["Source A"],
            "note": "Insufficient coverage for assessment.",
        }
    ],
    "meta_fractures": [
        {
            "name": "Speed versus oversight",
            "description": "Recurring conflict across situations.",
            "situation_indices": [0, 1],
            "shared_point": "Both treat the deadline as given.",
        }
    ],
    "metadata": {
        "articles_analyzed": 42,
        "clusters_total": 5,
        "clusters_analyzed": 2,
        "clusters_thin": 1,
        "analysis_threshold": "2+ articles",
        "generated_at": "2026-05-15T10:43:37.873249",
        "prediction_check": {
            "checked": 4,
            "triggered": 1,
            "contradicted": 1,
            "still_open": 2,
            "expired": 0,
        },
        "decision_routing": [
            {
                "decision": "Whether to bid on the follow-on",
                "factors": [
                    {"name": "Protest risk", "direction": "complicates"},
                    {"name": "Incumbent advantage", "direction": "supports"},
                ],
            }
        ],
    },
}


@pytest.fixture
def brief_document() -> BriefDocument:
    """A representative document exercising every renderable section."""
    return BriefDocument.from_synthesis_data(
        SYNTHESIS_DATA,
        articles_analyzed=42,
        synthesis_id=176,
        analysis_run_id=15,
        generated_at="2026-05-15T10:43:37.873249",
    )


# One realistic institutional-activity reading, on a beat that has been running
# for a while. Deliberately mixed: something spiking, something that has gone
# quiet after being active, something appearing for the first time, and two
# entities sitting on their baseline. No entry here names a natural person, and
# the payload has no field that could carry one.
INSTITUTIONAL_ACTIVITY: dict[str, Any] = {
    "window": 5,
    "items_scanned": 42,
    "never_observed": 3,
    "entities": [
        {
            "kind": "org",
            "name": "FedRAMP PMO",
            "count": 6,
            "trailing_average": 1.0,
            "prior_runs": 5,
            "movement": "up",
        },
        {
            "kind": "org",
            "name": "GSA",
            "count": 2,
            "trailing_average": 2.0,
            "prior_runs": 5,
            "movement": "unchanged",
        },
        {
            "kind": "org",
            "name": "OMB",
            "count": 0,
            "trailing_average": 3.4,
            "prior_runs": 5,
            "movement": "down",
        },
        {
            "kind": "program",
            "name": "CMMC",
            "count": 0,
            "trailing_average": 0.2,
            "prior_runs": 5,
            "movement": "unchanged",
        },
        {
            "kind": "document_type",
            "name": "Emergency Directive",
            "count": 1,
            "trailing_average": None,
            "prior_runs": 0,
            "movement": "first_run",
        },
    ],
}


@pytest.fixture
def activity_document() -> BriefDocument:
    """A beat brief carrying an institutional activity reading."""
    data = {
        **SYNTHESIS_DATA,
        "metadata": {
            **SYNTHESIS_DATA["metadata"],
            "institutional_activity": INSTITUTIONAL_ACTIVITY,
        },
    }
    return BriefDocument.from_synthesis_data(
        data,
        articles_analyzed=42,
        synthesis_id=176,
        analysis_run_id=15,
        generated_at="2026-05-15T10:43:37.873249",
    )


@pytest.fixture
def empty_document() -> BriefDocument:
    """A document where nothing met the analysis threshold."""
    return BriefDocument.from_synthesis_data({"metadata": {"articles_analyzed": 0}})


@pytest.fixture
def hostile_document() -> BriefDocument:
    """A document whose content contains HTML metacharacters."""
    return BriefDocument.from_synthesis_data(
        {
            "situations": [
                {
                    "title": "<script>alert('x')</script> & friends",
                    "narrative": 'A <b>bold</b> claim & an "aside".',
                    "actors": [{"name": "<img src=x onerror=1>", "role": "a & b"}],
                }
            ],
            "metadata": {"articles_analyzed": 1},
        }
    )


# A realistic standing agenda for a compliance beat: one question the week's
# coverage moved, one that has moved before but not this run, and one that has
# never moved at all. The last two are the reason this fixture exists (added
# 2026-08-26, backlog task 007).
STANDING_AGENDA = [
    {
        "question_id": 31,
        "text": "Does CMMC Phase 2 slip past its statutory date?",
        "status": "open",
        "declared_at": "2026-05-02",
        "moved": True,
        "moved_in": [
            {"situation_index": 1, "title": "Procurement rule change lands^[1]"},
        ],
        "appearance_count": 4,
        "last_moved_at": "2026-05-08",
        "watching": ["DFARS class deviation -- published before the statutory date"],
    },
    {
        "question_id": 32,
        "text": "Which CSPs move to FedRAMP authorized, and at which impact level?",
        "status": "open",
        "declared_at": "2026-05-02",
        "moved": False,
        "moved_in": [],
        "appearance_count": 2,
        "last_moved_at": "2026-05-08",
        "watching": [],
    },
    {
        "question_id": 33,
        "text": (
            "Where do GovRAMP and TX-RAMP diverge from FedRAMP in ways that "
            "matter to a multi-state CSP?"
        ),
        "status": "open",
        "declared_at": "2026-05-02",
        "moved": False,
        "moved_in": [],
        "appearance_count": 0,
        "last_moved_at": None,
        "watching": [],
    },
]


@pytest.fixture
def beat_document() -> BriefDocument:
    """A beat run's document, carrying a declared standing agenda."""
    data = {
        **SYNTHESIS_DATA,
        "metadata": {**SYNTHESIS_DATA["metadata"], "standing_agenda": STANDING_AGENDA},
    }
    return BriefDocument.from_synthesis_data(
        data,
        articles_analyzed=42,
        synthesis_id=177,
        analysis_run_id=16,
        generated_at="2026-05-15T10:43:37.873249",
    )


@pytest.fixture
def full_beat_document() -> BriefDocument:
    """
    A beat run carrying *both* beat sections at once.

    Tasks 006 and 007 each added a section to the same render path and were
    built from the same base, so nothing before this fixture ever rendered them
    together. This is what pins that they compose rather than one silently
    winning (added 2026-08-26 when 007 was rebased onto 006).
    """
    data = {
        **SYNTHESIS_DATA,
        "metadata": {
            **SYNTHESIS_DATA["metadata"],
            "standing_agenda": STANDING_AGENDA,
            "institutional_activity": INSTITUTIONAL_ACTIVITY,
        },
    }
    return BriefDocument.from_synthesis_data(
        data,
        articles_analyzed=42,
        synthesis_id=178,
        analysis_run_id=17,
        generated_at="2026-05-15T10:43:37.873249",
    )
