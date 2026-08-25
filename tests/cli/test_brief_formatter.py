"""
Tests for brief_formatter — focused on the question-identity render integration.
"""

import re

from src.cli.brief_formatter import BriefFormatter

# The formatting helpers moved to src/render/_text.py when brief rendering was
# split out; BriefFormatter is now a thin adapter over the renderers. These
# tests still exercise the same behaviour through the same public entry point.
from src.render._text import (
    decision_summary as _decision_summary,
)
from src.render._text import (
    prediction_check_line as _prediction_check_line,
)
from src.render._text import (
    question_lines as _question_lines,
)
from src.render._text import (
    watch_items as _watch_items,
)


def strip_ansi(text: str) -> str:
    """Drop ANSI color escapes so assertions can match on raw content."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestQuestionLines:
    def test_returns_empty_when_no_questions(self):
        assert _question_lines({}) == ("", "", [])

    def test_legacy_string_unresolved_question(self):
        text, prefix, secondary = _question_lines({"unresolved_question": "Will A?"})
        assert text == "Will A?"
        assert prefix == ""
        assert secondary == []

    def test_new_shape_first_run_has_new_prefix(self):
        out = _question_lines(
            {
                "unresolved_questions": {
                    "primary": {
                        "text": "Will A?",
                        "question_id": 7,
                        "first_asked_at": "2026-05-12T10:00:00",
                        "appearance_count": 1,
                    },
                    "secondary": [],
                }
            }
        )
        assert out[0] == "Will A?"
        assert out[1] == "Q7 (new)"
        assert out[2] == []

    def test_new_shape_returning_question_shows_run_and_date(self):
        out = _question_lines(
            {
                "unresolved_questions": {
                    "primary": {
                        "text": "Will A?",
                        "question_id": 7,
                        "first_asked_at": "2026-03-12T10:00:00",
                        "appearance_count": 4,
                    },
                    "secondary": [
                        {
                            "text": "Will B?",
                            "question_id": 8,
                            "first_asked_at": "2026-05-01T08:00:00",
                            "appearance_count": 2,
                        }
                    ],
                }
            }
        )
        assert out[0] == "Will A?"
        assert out[1] == "Q7 (run 4, asked 2026-03-12)"
        assert out[2] == [("Will B?", "Q8 (run 2, asked 2026-05-01)")]


class TestPredictionCheckLine:
    def test_empty_when_no_check(self):
        assert _prediction_check_line(None) == ""
        assert _prediction_check_line({}) == ""

    def test_empty_when_nothing_checked_or_expired(self):
        assert _prediction_check_line({"checked": 0, "expired": 0}) == ""

    def test_renders_summary(self):
        line = _prediction_check_line(
            {
                "checked": 10,
                "triggered": 2,
                "contradicted": 1,
                "still_open": 7,
                "expired": 3,
            }
        )
        assert "10 open observables graded" in line
        assert "2 triggered" in line
        assert "1 contradicted" in line
        assert "7 still open" in line
        assert "3 expired" in line

    def test_renders_when_only_expired(self):
        line = _prediction_check_line({"checked": 0, "expired": 4})
        assert "4 expired" in line


class TestWatchItems:
    def test_list_of_objects(self):
        futures = {
            "what_to_watch": [
                {"observable": "Fed cuts", "trigger_condition": "cut announced"},
                {"observable": "Yield inverts", "trigger_condition": "2y > 10y"},
            ]
        }
        assert _watch_items(futures) == [
            "Fed cuts -- cut announced",
            "Yield inverts -- 2y > 10y",
        ]

    def test_legacy_string(self):
        assert _watch_items({"what_to_watch": "Watch the Fed"}) == ["Watch the Fed"]

    def test_observable_only(self):
        assert _watch_items({"what_to_watch": [{"observable": "Just this"}]}) == ["Just this"]

    def test_empty(self):
        assert _watch_items({}) == []
        assert _watch_items({"what_to_watch": []}) == []


class TestMetaFractures:
    def _report_with_meta(self, mfs):
        return {
            "synthesis_data": {
                "situations": [
                    {"title": "S1", "narrative": "a"},
                    {"title": "S2", "narrative": "b"},
                ],
                "thin_coverage": [],
                "meta_fractures": mfs,
                "metadata": {"articles_analyzed": 2},
            }
        }

    def test_terminal_renders_meta_fractures(self):
        report = self._report_with_meta(
            [
                {
                    "name": "labor capacity fracture",
                    "description": "Whether the labor pool can absorb demand.",
                    "situation_indices": [0, 1],
                    "shared_point": "Workforce constraints.",
                }
            ]
        )
        out = strip_ansi(BriefFormatter().format_report(report))
        assert "META-FRACTURES" in out
        assert "labor capacity fracture" in out
        assert "Appears in: Situation 1, Situation 2" in out
        assert "Workforce constraints." in out

    def test_terminal_skips_when_empty(self):
        report = self._report_with_meta([])
        out = strip_ansi(BriefFormatter().format_report(report))
        assert "META-FRACTURES" not in out

    def test_markdown_renders_meta_fractures(self):
        report = self._report_with_meta(
            [
                {
                    "name": "labor capacity fracture",
                    "description": "Whether the labor pool can absorb demand.",
                    "situation_indices": [0, 1],
                    "shared_point": "Workforce constraints.",
                }
            ]
        )
        md = BriefFormatter().format_markdown(report)
        assert "## Meta-fractures" in md
        assert "### labor capacity fracture" in md
        assert "Whether the labor pool can absorb demand." in md
        assert "Workforce constraints." in md


class TestDecisionSummary:
    def test_empty_when_no_routing(self):
        assert _decision_summary({}) == []
        assert _decision_summary({"decision_routing": "not a list"}) == []

    def test_returns_routing_list(self):
        routing = [
            {"decision": "housing", "factors": [{"name": "rates", "direction": "complicates"}]}
        ]
        assert _decision_summary({"decision_routing": routing}) == routing

    def test_terminal_renders_decision_section(self):
        report = {
            "synthesis_data": {
                "situations": [],
                "thin_coverage": [],
                "metadata": {
                    "articles_analyzed": 3,
                    "decision_routing": [
                        {
                            "decision": "housing market monitoring",
                            "factors": [
                                {"name": "interest rates", "direction": "complicates"},
                                {"name": "inventory", "direction": "supports"},
                            ],
                        }
                    ],
                },
            }
        }
        out = strip_ansi(BriefFormatter().format_report(report))
        assert "YOUR DECISIONS" in out
        assert "housing market monitoring" in out
        assert "interest rates" in out
        assert "complicates" in out
        assert "[-]" in out  # complicates glyph
        assert "[+]" in out  # supports glyph

    def test_markdown_renders_decision_section(self):
        report = {
            "synthesis_data": {
                "situations": [],
                "thin_coverage": [],
                "metadata": {
                    "articles_analyzed": 3,
                    "decision_routing": [
                        {
                            "decision": "career move",
                            "factors": [{"name": "salary range", "direction": "supports"}],
                        }
                    ],
                },
            }
        }
        md = BriefFormatter().format_markdown(report)
        assert "## Your decisions" in md
        assert "### career move" in md
        assert "**salary range** — supports" in md


class TestRenderIntegration:
    """Full-report renders surface the question prefix in both terminal and md."""

    def _report(self, primary: dict, secondary: list[dict] | None = None) -> dict:
        return {
            "synthesis_data": {
                "situations": [
                    {
                        "title": "Test situation",
                        "narrative": "Paragraph.",
                        "where_this_goes": {
                            "branching_paths": "If X then Y.",
                            "unresolved_questions": {
                                "primary": primary,
                                "secondary": secondary or [],
                            },
                            "what_to_watch": "An event.",
                        },
                    }
                ],
                "thin_coverage": [],
                "metadata": {
                    "articles_analyzed": 3,
                    "clusters_analyzed": 1,
                    "clusters_thin": 0,
                    "analysis_threshold": "2+ articles",
                },
            }
        }

    def test_terminal_first_run_shows_new_tag(self):
        report = self._report(
            primary={
                "text": "Will A?",
                "question_id": 7,
                "first_asked_at": "2026-05-12T10:00:00",
                "appearance_count": 1,
            }
        )
        out = strip_ansi(BriefFormatter().format_report(report))
        assert "Key question:" in out
        assert "Q7 (new)" in out
        assert "Will A?" in out

    def test_terminal_returning_question_shows_run_count(self):
        report = self._report(
            primary={
                "text": "Will A?",
                "question_id": 7,
                "first_asked_at": "2026-03-12T10:00:00",
                "appearance_count": 4,
            }
        )
        out = strip_ansi(BriefFormatter().format_report(report))
        assert "Q7 (run 4, asked 2026-03-12)" in out

    def test_markdown_renders_question_prefix(self):
        report = self._report(
            primary={
                "text": "Will A?",
                "question_id": 7,
                "first_asked_at": "2026-03-12T10:00:00",
                "appearance_count": 4,
            },
            secondary=[
                {
                    "text": "Will B?",
                    "question_id": 8,
                    "first_asked_at": "2026-05-01T08:00:00",
                    "appearance_count": 1,
                }
            ],
        )
        md = BriefFormatter().format_markdown(report)
        assert "**Key question:**" in md
        assert "Q7 (run 4, asked 2026-03-12)" in md
        assert "Will A?" in md
        assert "Q8 (new)" in md
        assert "Will B?" in md

    def test_markdown_legacy_string_shape_still_renders(self):
        # A synthesis emitted under the old prompt shape -- string field.
        report = {
            "synthesis_data": {
                "situations": [
                    {
                        "title": "Legacy",
                        "narrative": "X.",
                        "where_this_goes": {
                            "unresolved_question": "Old single question?",
                        },
                    }
                ],
                "thin_coverage": [],
                "metadata": {"articles_analyzed": 1},
            }
        }
        md = BriefFormatter().format_markdown(report)
        assert "Old single question?" in md
