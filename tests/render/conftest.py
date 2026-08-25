"""
Fixtures for the renderer tests.

Every fixture here is a plain in-memory ``BriefDocument``. Nothing in this
package touches the pipeline, the database, the network or Claude: rendering
is a pure function of a document, and these tests are what pins that down.
"""

import pytest

from src.render.document import BriefDocument

SYNTHESIS_DATA = {
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
