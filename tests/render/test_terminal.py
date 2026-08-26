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


class TestInstitutionalActivity:
    """
    The section reads like an analyst noting movement, not like a dashboard.
    What is pinned: the sentence forms, that steady entities survive, that
    nothing is ordered by count, and that a brief without a reading gains no
    section at all.
    """

    def test_absent_when_the_run_recorded_none(self, brief_document):
        out = strip_ansi(TerminalRenderer().render(brief_document))
        assert "INSTITUTIONAL ACTIVITY" not in out

    def test_section_header_and_disclaimer(self, activity_document):
        out = strip_ansi(TerminalRenderer().render(activity_document))
        assert "INSTITUTIONAL ACTIVITY" in out
        assert "not a measure of significance" in out

    def test_a_spike_states_the_baseline_it_departed_from(self, activity_document):
        out = strip_ansi(TerminalRenderer().render(activity_document))
        assert "FedRAMP PMO appeared in 6 items this run, against a trailing average of 1." in out

    def test_a_drop_to_silence_is_stated_the_same_way(self, activity_document):
        out = strip_ansi(TerminalRenderer().render(activity_document))
        assert "OMB appeared in 0 items this run, against a trailing average of 3.4." in out

    def test_a_first_observation_says_it_has_no_baseline(self, activity_document):
        out = strip_ansi(TerminalRenderer().render(activity_document))
        assert "Emergency Directive appeared in 1 item this run; no trailing average yet." in out

    def test_steady_entities_are_kept_not_dropped(self, activity_document):
        """Silence is information; a section showing only increases is a scoreboard."""
        out = strip_ansi(TerminalRenderer().render(activity_document))
        assert "CMMC appeared in 0, unchanged." in out
        assert "GSA appeared in 2, unchanged." in out

    def test_never_mentioned_entities_are_accounted_for_but_not_named(self, activity_document):
        out = strip_ansi(TerminalRenderer().render(activity_document))
        assert "3 declared entities have never been mentioned and are not listed." in out

    def test_movers_precede_steady_entities_but_neither_is_ranked_by_count(self, activity_document):
        out = strip_ansi(TerminalRenderer().render(activity_document))
        section = out.split("INSTITUTIONAL ACTIVITY")[1]
        order = [
            line
            for name in ("FedRAMP PMO", "OMB", "Emergency Directive", "GSA", "CMMC")
            for line in [section.index(name)]
        ]
        assert order == sorted(order), "movers first, then steady, each in config order"

    def test_is_deterministic(self, activity_document):
        renderer = TerminalRenderer()
        assert renderer.render(activity_document) == renderer.render(activity_document)
