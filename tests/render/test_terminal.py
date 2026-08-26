"""
Tests for TerminalRenderer against a fixture BriefDocument.
"""

import re

from src.render.terminal import TerminalRenderer


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestRender:
    def test_is_deterministic(self, brief_document):
        renderer = TerminalRenderer()
        assert renderer.render(brief_document) == renderer.render(brief_document)

    def test_two_renderer_instances_agree(self, brief_document):
        assert TerminalRenderer().render(brief_document) == TerminalRenderer().render(
            brief_document
        )

    def test_header_and_metadata_line(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "INTELLIGENCE BRIEF" in out
        assert (
            "Articles: 42 | Situations: 2 analyzed, 1 thin coverage | Threshold: 2+ articles" in out
        )

    def test_prediction_check_line(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "Prediction check: 4 open observables graded" in out

    def test_decisions_section(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "YOUR DECISIONS" in out
        assert "Whether to bid on the follow-on" in out
        assert "[-] Protest risk (complicates)" in out
        assert "[+] Incumbent advantage (supports)" in out

    def test_situation_sections(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "SITUATION 1: Procurement rule change lands[1]" in out
        assert "SITUATION 2: A second situation with no optional blocks" in out
        assert "ACTORS:" in out
        assert "POWER DYNAMICS:" in out
        assert "WHAT THE COVERAGE MAKES VISIBLE AND INVISIBLE:" in out
        assert "WHERE THIS GOES:" in out
        assert "INFORMATION GAPS:" in out

    def test_citations_are_cleaned_in_titles_and_narrative(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "^[1]" not in out.split("Bridges:")[0]
        assert "First paragraph with a citation[1]." in out

    def test_question_identity_prefixes(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "Q7 (run 3, asked 2026-01-04) Will the protest be sustained?" in out
        assert "Q9 (new) Who audits the waiver?" in out

    def test_watch_items_include_both_shapes(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "Watch for: GAO docket entry -- filed within 10 days" in out
        assert "Watch for: A bare observable" in out

    def test_meta_fracture_and_thin_coverage_sections(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "META-FRACTURES" in out
        assert "Appears in: Situation 1, Situation 2" in out
        assert "THIN COVERAGE" in out
        assert "Single-article topic" in out

    def test_empty_document(self, empty_document):
        out = strip_ansi(TerminalRenderer().render(empty_document))
        assert "No situations met the analysis threshold." in out
        assert "META-FRACTURES" not in out
        assert "THIN COVERAGE" not in out

    def test_wraps_narrative_to_max_width(self, brief_document):
        out = strip_ansi(TerminalRenderer(max_width=40).render(brief_document))
        narrative_lines = [line for line in out.splitlines() if line.startswith("First paragraph")]
        assert narrative_lines
        assert all(len(line) <= 40 for line in narrative_lines)


class TestRenderCompact:
    def test_lists_titles_and_counts(self, brief_document):
        out = strip_ansi(TerminalRenderer().render_compact(brief_document))
        assert "Situations analyzed:" in out
        assert "1. Procurement rule change lands[1]" in out
        assert "+ 1 topics with thin coverage" in out
        assert "Articles: 42 | Clusters: 5" in out

    def test_is_deterministic(self, brief_document):
        renderer = TerminalRenderer()
        assert renderer.render_compact(brief_document) == renderer.render_compact(brief_document)

    def test_omits_empty_sections(self, empty_document):
        out = strip_ansi(TerminalRenderer().render_compact(empty_document))
        assert "Situations analyzed:" not in out
        assert "thin coverage" not in out


class TestOneLineSummary:
    def test_counts_articles_and_situations(self, brief_document):
        assert (
            TerminalRenderer().render_one_line_summary(brief_document)
            == "BRIEF: 42 articles, 2 situations analyzed"
        )
