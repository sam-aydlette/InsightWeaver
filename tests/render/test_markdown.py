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
