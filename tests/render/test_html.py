"""
Tests for HTMLRenderer against a fixture BriefDocument.

The load-bearing property is self-containment: the page must render with no
network access at all, so nothing may reference an external resource.
"""

import re

from src.render.html import HTMLRenderer

# Tags that can pull in a remote resource, and attributes that point at one.
FETCHING_TAGS = ("script", "img", "link", "iframe", "object", "embed", "video", "audio", "source")
FETCHING_ATTRS = ("src", "href", "srcset", "data", "poster", "action")


def external_resource_hits(html: str) -> list[str]:
    """
    Every construct in ``html`` that would make a browser issue a request.

    Only real markup counts: content is HTML-escaped, so a literal ``<`` is the
    start of a tag the renderer emitted, while escaped text like
    ``&lt;img src=x&gt;`` is inert and must not register.
    """
    hits = []
    for tag in re.findall(r"<[^>]*>", html):
        name = re.match(r"</?\s*([a-zA-Z0-9-]+)", tag)
        if name and name.group(1).lower() in FETCHING_TAGS:
            hits.append(tag)
            continue
        for attr in FETCHING_ATTRS:
            if re.search(rf"\b{attr}\s*=", tag, re.IGNORECASE):
                hits.append(tag)
                break
    # CSS can fetch too, and it lives outside any tag.
    hits.extend(re.findall(r"@import[^;]*;|url\([^)]*\)", html, re.IGNORECASE))
    return hits


class TestSelfContainment:
    def test_references_no_external_resource(self, brief_document):
        assert external_resource_hits(HTMLRenderer().render(brief_document)) == []

    def test_styles_are_inline(self, brief_document):
        html = HTMLRenderer().render(brief_document)
        assert "<style>" in html
        assert "font-family" in html

    def test_is_a_complete_document(self, brief_document):
        html = HTMLRenderer().render(brief_document)
        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")
        assert '<meta charset="utf-8">' in html


class TestDeterminism:
    def test_same_document_renders_the_same_bytes(self, brief_document):
        renderer = HTMLRenderer()
        assert renderer.render(brief_document) == renderer.render(brief_document)

    def test_two_instances_agree(self, brief_document):
        assert HTMLRenderer().render(brief_document) == HTMLRenderer().render(brief_document)

    def test_title_comes_from_stored_date_not_the_clock(self, brief_document):
        assert HTMLRenderer().title(brief_document) == "Intelligence Brief — 2026-05-15"

    def test_title_without_a_stored_date(self, empty_document):
        assert HTMLRenderer().title(empty_document) == "Intelligence Brief"


class TestContent:
    def test_carries_every_section(self, brief_document):
        html = HTMLRenderer().render(brief_document)
        assert "<h1>Intelligence Brief</h1>" in html
        assert "Your decisions" in html
        assert "Situation 1: Procurement rule change lands[1]" in html
        assert "Situation 2: A second situation with no optional blocks" in html
        assert "Meta-fractures" in html
        assert "Thin coverage" in html

    def test_metadata_and_provenance(self, brief_document):
        html = HTMLRenderer().render(brief_document)
        assert "Articles: 42 | Situations: 2 analyzed, 1 thin coverage" in html
        assert "Stored brief #176" in html
        assert "Prediction check: 4 open observables graded" in html

    def test_narrative_paragraphs_are_split(self, brief_document):
        html = HTMLRenderer().render(brief_document)
        assert "<p>First paragraph with a citation[1].</p>" in html
        assert "<p>Second paragraph[2].</p>" in html

    def test_questions_and_watch_items(self, brief_document):
        html = HTMLRenderer().render(brief_document)
        assert "Will the protest be sustained?" in html
        assert "Q7 (run 3, asked 2026-01-04)" in html
        assert "GAO docket entry -- filed within 10 days" in html

    def test_information_gaps(self, brief_document):
        html = HTMLRenderer().render(brief_document)
        assert "The waiver text itself" in html
        assert "Suggested source: Agency press office feed" in html

    def test_empty_document(self, empty_document):
        html = HTMLRenderer().render(empty_document)
        assert "No situations met the analysis threshold." in html
        assert "Meta-fractures" not in html
        assert "Thin coverage" not in html


class TestEscaping:
    def test_markup_in_content_is_escaped(self, hostile_document):
        html = HTMLRenderer().render(hostile_document)
        assert "<script>alert" not in html
        assert "&lt;script&gt;alert" in html
        assert "&lt;img src=x onerror=1&gt;" in html
        assert "&amp; friends" in html

    def test_content_that_looks_like_markup_fetches_nothing(self, hostile_document):
        # The fixture actor name is literally `<img src=x onerror=1>`; escaped,
        # it is inert text, so the page still references no external resource.
        assert external_resource_hits(HTMLRenderer().render(hostile_document)) == []


class TestInstitutionalActivity:
    def test_absent_when_the_run_recorded_none(self, brief_document):
        assert "Institutional activity" not in HTMLRenderer().render(brief_document)

    def test_section_carries_movement_and_steady_lines(self, activity_document):
        html = HTMLRenderer().render(activity_document)
        assert "<h2>Institutional activity</h2>" in html
        assert (
            "<li>FedRAMP PMO appeared in 6 items this run, "
            "against a trailing average of 1.</li>" in html
        )
        assert '<li class="muted">CMMC appeared in 0, unchanged.</li>' in html
        assert "3 declared entities have never been mentioned and are not listed." in html

    def test_is_deterministic(self, activity_document):
        assert HTMLRenderer().render(activity_document) == HTMLRenderer().render(activity_document)


class TestStandingAgendaHTML:
    """Every declared question, moved or not, survives into the HTML copy."""

    def test_section_absent_without_a_declared_agenda(self, brief_document):
        assert "<h2>Standing agenda</h2>" not in HTMLRenderer().render(brief_document)

    def test_every_declared_question_appears(self, beat_document):
        out = HTMLRenderer().render(beat_document)
        assert "<h2>Standing agenda</h2>" in out
        assert "[MOVED] Does CMMC Phase 2 slip past its statutory date?" in out
        assert "[NO MOVEMENT] Which CSPs move to FedRAMP authorized" in out
        assert "[NO MOVEMENT] Where do GovRAMP and TX-RAMP diverge" in out

    def test_never_moved_question_says_so_explicitly(self, beat_document):
        out = HTMLRenderer().render(beat_document)
        assert "No coverage this run bore on this question, and none ever has." in out


class TestBeatSectionsComposeHTML:
    def test_both_sections_render_in_order(self, full_beat_document):
        out = HTMLRenderer().render(full_beat_document)
        assert "<h2>Standing agenda</h2>" in out
        assert "<h2>Institutional activity</h2>" in out
        assert out.index("<h2>Standing agenda</h2>") < out.index("<h2>Institutional activity</h2>")

    def test_neither_section_loses_its_quiet_entries(self, full_beat_document):
        out = HTMLRenderer().render(full_beat_document)
        assert "No coverage this run bore on this question, and none ever has." in out
        assert "OMB appeared in 0 items this run" in out
