"""
Tests for MarkdownRenderer against a fixture BriefDocument.
"""

from src.render.markdown import MarkdownRenderer


class TestRender:
    def test_is_deterministic(self, brief_document):
        renderer = MarkdownRenderer()
        assert renderer.render(brief_document) == renderer.render(brief_document)

    def test_headings(self, brief_document):
        md = MarkdownRenderer().render(brief_document)
        assert md.startswith("# Intelligence Brief")
        assert "## Situation 1: Procurement rule change lands[1]" in md
        assert "## Meta-fractures" in md
        assert "## Thin coverage" in md
        assert "## Your decisions" in md

    def test_metadata_line(self, brief_document):
        md = MarkdownRenderer().render(brief_document)
        assert (
            "_Articles: 42 | Situations: 2 analyzed, 1 thin coverage | Threshold: 2+ articles_"
            in md
        )

    def test_situation_subsections(self, brief_document):
        md = MarkdownRenderer().render(brief_document)
        assert "### Actors" in md
        assert "### Power dynamics" in md
        assert "### Where this goes" in md
        assert "### Information gaps" in md

    def test_question_identity_prefixes(self, brief_document):
        md = MarkdownRenderer().render(brief_document)
        assert "_Q7 (run 3, asked 2026-01-04)_ Will the protest be sustained?" in md
        assert "_Q9 (new)_ Who audits the waiver?" in md

    def test_carries_no_ansi_escapes(self, brief_document):
        assert "\x1b[" not in MarkdownRenderer().render(brief_document)

    def test_empty_document(self, empty_document):
        md = MarkdownRenderer().render(empty_document)
        assert "_No situations met the analysis threshold._" in md
        assert "## Thin coverage" not in md


class TestInstitutionalActivity:
    def test_absent_when_the_run_recorded_none(self, brief_document):
        assert "## Institutional activity" not in MarkdownRenderer().render(brief_document)

    def test_section_carries_movement_and_steady_lines(self, activity_document):
        md = MarkdownRenderer().render(activity_document)
        assert "## Institutional activity" in md
        assert "- FedRAMP PMO appeared in 6 items this run, against a trailing average of 1." in md
        assert "- OMB appeared in 0 items this run, against a trailing average of 3.4." in md
        assert "- _CMMC appeared in 0, unchanged._" in md
        assert "_3 declared entities have never been mentioned and are not listed._" in md

    def test_is_deterministic(self, activity_document):
        assert MarkdownRenderer().render(activity_document) == MarkdownRenderer().render(
            activity_document
        )


class TestStandingAgendaMarkdown:
    """Every declared question, moved or not, survives into the archival copy."""

    def test_section_absent_without_a_declared_agenda(self, brief_document):
        assert "## Standing agenda" not in MarkdownRenderer().render(brief_document)

    def test_every_declared_question_appears(self, beat_document):
        out = MarkdownRenderer().render(beat_document)
        assert "## Standing agenda" in out
        for entry in beat_document.standing_agenda:
            assert entry["text"] in out

    def test_moved_and_unmoved_are_labelled(self, beat_document):
        out = MarkdownRenderer().render(beat_document)
        assert "### [MOVED] Does CMMC Phase 2 slip past its statutory date?" in out
        assert "### [NO MOVEMENT] Which CSPs move to FedRAMP authorized" in out
        assert "**Moved in:** Situation 1: Procurement rule change lands[1]" in out

    def test_never_moved_question_says_so_explicitly(self, beat_document):
        out = MarkdownRenderer().render(beat_document)
        assert "No coverage this run bore on this question, and none ever has." in out


class TestBeatSectionsComposeMarkdown:
    def test_both_sections_render_in_order(self, full_beat_document):
        out = MarkdownRenderer().render(full_beat_document)
        assert "## Standing agenda" in out
        assert "## Institutional activity" in out
        assert out.index("## Standing agenda") < out.index("## Institutional activity")

    def test_neither_section_loses_its_quiet_entries(self, full_beat_document):
        out = MarkdownRenderer().render(full_beat_document)
        assert "No coverage this run bore on this question, and none ever has." in out
        assert "OMB appeared in 0 items this run" in out
