"""
Tests for brief_formatter — focused on the question-identity render integration.
"""

import re

from src.cli.brief_formatter import BriefFormatter, _question_lines


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
