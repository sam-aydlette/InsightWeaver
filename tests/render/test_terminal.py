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


class TestStandingAgenda:
    """
    The section that makes the brief a delta against a declared agenda.

    Note what every one of these asserts: the quiet questions are present.
    A renderer that dropped them would still pass every other test in this
    file, which is why these exist (added 2026-08-26, backlog task 007).
    """

    def test_section_absent_without_a_declared_agenda(self, brief_document):
        assert "STANDING AGENDA" not in strip_ansi(TerminalRenderer().render(brief_document))

    def test_every_declared_question_appears(self, beat_document):
        out = strip_ansi(TerminalRenderer().render(beat_document))
        assert "STANDING AGENDA" in out
        for entry in beat_document.standing_agenda:
            assert entry["text"] in out

    def test_moved_question_names_its_situation(self, beat_document):
        out = strip_ansi(TerminalRenderer().render(beat_document))
        assert "[MOVED] Does CMMC Phase 2 slip past its statutory date?" in out
        assert "Moved in: Situation 1: Procurement rule change lands[1]" in out
        assert "Q31 (declared 2026-05-02, run 4)" in out

    def test_previously_moved_question_says_when_it_last_moved(self, beat_document):
        out = strip_ansi(TerminalRenderer().render(beat_document))
        assert "[NO MOVEMENT] Which CSPs move to FedRAMP authorized" in out
        assert "No coverage this run bore on this question. Last moved 2026-05-08." in out
        assert "Q32 (declared 2026-05-02, 2 prior run(s), last moved 2026-05-08)" in out

    def test_never_moved_question_says_so_explicitly(self, beat_document):
        out = strip_ansi(TerminalRenderer().render(beat_document))
        assert "[NO MOVEMENT] Where do GovRAMP and TX-RAMP diverge" in out
        assert "No coverage this run bore on this question, and none ever has." in out
        assert "Q33 (declared 2026-05-02, never moved)" in out

    def test_open_observable_is_shown(self, beat_document):
        out = strip_ansi(TerminalRenderer().render(beat_document))
        assert "Watching for: DFARS class deviation -- published before the statutory date" in out

    def test_agenda_precedes_the_situations(self, beat_document):
        out = strip_ansi(TerminalRenderer().render(beat_document))
        assert out.index("STANDING AGENDA") < out.index("SITUATION 1:")

    def test_is_deterministic(self, beat_document):
        renderer = TerminalRenderer()
        assert renderer.render(beat_document) == renderer.render(beat_document)


class TestBeatSectionsCompose:
    """
    Both beat sections in one brief.

    Tasks 006 and 007 extended the same render path from the same base. These
    assert the merged behaviour neither task could have tested alone: both
    sections present, in a fixed order, with nothing lost from either.
    """

    def test_both_sections_render(self, full_beat_document):
        out = strip_ansi(TerminalRenderer().render(full_beat_document))
        assert "STANDING AGENDA" in out
        assert "INSTITUTIONAL ACTIVITY" in out

    def test_standing_agenda_leads_and_activity_follows_the_situations(self, full_beat_document):
        """
        The declared agenda is what the beat committed to watching before any
        coverage arrived, so it leads. The activity reading is a measurement
        over the same items the situations are drawn from, so it follows them
        as supporting evidence rather than as the agenda.
        """
        out = strip_ansi(TerminalRenderer().render(full_beat_document))
        assert (
            out.index("STANDING AGENDA")
            < out.index("SITUATION 1:")
            < out.index("INSTITUTIONAL ACTIVITY")
            < out.index("THIN COVERAGE")
        )

    def test_neither_section_loses_its_quiet_entries(self, full_beat_document):
        """
        Both features exist to report absence. Rendering them together must not
        drop either one's silent rows.
        """
        out = strip_ansi(TerminalRenderer().render(full_beat_document))
        # 007: a standing question no coverage touched.
        assert "No coverage this run bore on this question, and none ever has." in out
        # 006: an office that has been active and said nothing this run.
        assert "OMB appeared in 0 items this run" in out

    def test_each_section_still_renders_alone(self, beat_document, activity_document):
        agenda_only = strip_ansi(TerminalRenderer().render(beat_document))
        activity_only = strip_ansi(TerminalRenderer().render(activity_document))
        assert "STANDING AGENDA" in agenda_only
        assert "INSTITUTIONAL ACTIVITY" not in agenda_only
        assert "INSTITUTIONAL ACTIVITY" in activity_only
        assert "STANDING AGENDA" not in activity_only

    def test_is_deterministic(self, full_beat_document):
        renderer = TerminalRenderer()
        assert renderer.render(full_beat_document) == renderer.render(full_beat_document)
