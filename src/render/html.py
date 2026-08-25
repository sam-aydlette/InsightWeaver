"""
HTML renderer.

Produces one self-contained document: inline stylesheet, no scripts, no web
fonts, no images, no external requests of any kind. Opening the file offline
renders exactly what was written. Output is a pure function of the
:class:`BriefDocument`, so rendering the same stored run twice is byte-identical.
"""

from __future__ import annotations

from html import escape

from ._text import (
    DIRECTION_GLYPH,
    clean_citations,
    decision_summary,
    prediction_check_line,
    question_lines,
    watch_items,
)
from .document import BriefDocument

__all__ = ["HTMLRenderer"]

# Deliberately small and self-contained: system font stack (no web fonts),
# no framework, no external assets. See OUT OF SCOPE in backlog/003.
STYLESHEET = """\
:root { color-scheme: light dark; }
body {
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
  max-width: 46rem;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 16px;
  line-height: 1.55;
  color: #1a1a1a;
  background: #ffffff;
}
h1 { font-size: 1.6rem; margin: 0 0 0.25rem; letter-spacing: 0.02em; }
h2 { font-size: 1.2rem; margin: 2.5rem 0 0.25rem; }
h3 { font-size: 0.95rem; margin: 1.5rem 0 0.35rem; text-transform: uppercase; letter-spacing: 0.06em; color: #444; }
p { margin: 0 0 0.9rem; }
ul { margin: 0 0 0.9rem; padding-left: 1.2rem; }
li { margin: 0 0 0.3rem; }
.meta { color: #555; font-size: 0.85rem; margin: 0 0 0.35rem; }
.rule { border: 0; border-top: 1px solid #d8d8d8; margin: 0.75rem 0 0; }
.section-note { color: #555; font-size: 0.85rem; font-style: italic; margin: 0 0 0.9rem; }
.situation { margin: 0 0 2.5rem; }
.label { color: #444; font-weight: 600; }
.muted { color: #555; }
.gap { color: #8a5a00; font-weight: 600; }
.tag { color: #555; font-size: 0.8rem; }
.glyph { display: inline-block; min-width: 1.4rem; font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; }
.empty { color: #555; font-style: italic; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e6e6; background: #161616; }
  h3, .meta, .section-note, .muted, .tag { color: #a8a8a8; }
  .label { color: #cfcfcf; }
  .rule { border-top-color: #3a3a3a; }
  .gap { color: #e0a33a; }
}
"""


class HTMLRenderer:
    """Render a :class:`BriefDocument` as one self-contained HTML page."""

    def render(self, doc: BriefDocument) -> str:
        body = self._body(doc)
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{escape(self.title(doc))}</title>\n"
            f"<style>\n{STYLESHEET}</style>\n"
            "</head>\n"
            "<body>\n"
            f"{body}\n"
            "</body>\n"
            "</html>\n"
        )

    def title(self, doc: BriefDocument) -> str:
        """Document title -- stable for a given stored run."""
        stamp = doc.date_stamp
        return f"Intelligence Brief — {stamp}" if stamp else "Intelligence Brief"

    # -- sections --------------------------------------------------------

    def _body(self, doc: BriefDocument) -> str:
        out: list[str] = ["<h1>Intelligence Brief</h1>"]

        stamp = doc.date_stamp
        if stamp:
            out.append(f'<p class="meta">Generated {escape(stamp)}</p>')

        metadata = doc.metadata
        out.append(
            '<p class="meta">'
            f"Articles: {escape(str(metadata.get('articles_analyzed', 0)))} | "
            f"Situations: {escape(str(metadata.get('clusters_analyzed', 0)))} analyzed, "
            f"{escape(str(metadata.get('clusters_thin', 0)))} thin coverage | "
            f"Threshold: {escape(str(metadata.get('analysis_threshold', '3+ articles')))}"
            "</p>"
        )

        check_line = prediction_check_line(metadata.get("prediction_check"))
        if check_line:
            out.append(f'<p class="meta">{escape(check_line)}</p>')

        if doc.synthesis_id is not None:
            out.append(f'<p class="meta">Stored brief #{escape(str(doc.synthesis_id))}</p>')

        out.append('<hr class="rule">')

        out.extend(self._decisions(doc))
        out.extend(self._situations(doc))
        out.extend(self._meta_fractures(doc))
        out.extend(self._thin_coverage(doc))

        return "\n".join(out)

    def _decisions(self, doc: BriefDocument) -> list[str]:
        decisions = decision_summary(doc.metadata)
        if not decisions:
            return []
        out = [
            "<h2>Your decisions</h2>",
            '<p class="section-note">What today\'s coverage moved.</p>',
        ]
        for entry in decisions:
            out.append(f"<h3>{escape(str(entry.get('decision', '(decision)')))}</h3>")
            factors = entry.get("factors", [])
            if factors:
                out.append("<ul>")
                for factor in factors:
                    direction = str(factor.get("direction", "neutral"))
                    glyph = DIRECTION_GLYPH.get(direction, "~")
                    name = str(factor.get("name", "(factor)"))
                    out.append(
                        f'<li><span class="glyph">[{escape(glyph)}]</span>{escape(name)} '
                        f'<span class="tag">({escape(direction)})</span></li>'
                    )
                out.append("</ul>")
        return out

    def _situations(self, doc: BriefDocument) -> list[str]:
        if not doc.situations:
            return ['<p class="empty">No situations met the analysis threshold.</p>']
        out: list[str] = []
        for index, situation in enumerate(doc.situations, 1):
            out.extend(self._situation(situation, index))
        return out

    def _situation(self, situation: dict, index: int) -> list[str]:
        title = clean_citations(str(situation.get("title", "Untitled situation")))
        out = ['<section class="situation">', f"<h2>Situation {index}: {escape(title)}</h2>"]

        narrative = situation.get("narrative", "")
        if narrative:
            for paragraph in clean_citations(str(narrative)).split("\n\n"):
                text = paragraph.strip()
                if text:
                    out.append(f"<p>{escape(text)}</p>")

        actors = situation.get("actors", [])
        if actors:
            out.append("<h3>Actors</h3>")
            out.append("<ul>")
            for actor in actors:
                name = escape(str(actor.get("name", "Unknown")))
                status = str(actor.get("epistemic_status", "") or "")
                status_tag = f' <span class="tag">[{escape(status)}]</span>' if status else ""
                details: list[str] = []
                if actor.get("role"):
                    details.append(f"Role: {escape(str(actor['role']))}")
                if actor.get("interests"):
                    details.append(f"Interests: {escape(str(actor['interests']))}")
                detail_html = ""
                if details:
                    detail_items = "".join(f"<li>{d}</li>" for d in details)
                    detail_html = f"<ul>{detail_items}</ul>"
                out.append(f'<li><span class="label">{name}</span>{status_tag}{detail_html}</li>')
            out.append("</ul>")

        power = situation.get("power_dynamics", {})
        if power:
            out.append("<h3>Power dynamics</h3>")
            out.extend(
                self._definition_list(
                    [
                        ("Benefits", power.get("who_benefits"), True),
                        ("Harmed", power.get("who_is_harmed"), True),
                        ("Decides", power.get("who_decides"), True),
                    ]
                )
            )

        frame = situation.get("coverage_frame", {})
        if frame:
            out.append("<h3>What the coverage makes visible and invisible</h3>")
            rows: list[tuple[str, object, bool]] = []
            if frame.get("narrative_layers"):
                rows.append(("Narratives", frame.get("narrative_layers"), False))
            elif frame.get("dominant_frame"):
                rows.append(("Frame", frame.get("dominant_frame"), False))
            rows.append(("Fractures", frame.get("fractures"), False))
            rows.append(("Bridges", frame.get("bridges"), False))
            rows.append(("Hard to see", frame.get("structural_absences"), False))
            rows.append(("Assumes", frame.get("assumed_premise"), False))
            out.extend(self._definition_list(rows))

        futures = situation.get("where_this_goes", {})
        if futures:
            out.append("<h3>Where this goes</h3>")
            rows = [("Paths", futures.get("branching_paths"), True)]
            out.extend(self._definition_list(rows))

            primary_text, primary_prefix, secondary = question_lines(futures)
            if primary_text or secondary:
                out.append("<ul>")
                if primary_text:
                    tag = (
                        f'<span class="tag">{escape(primary_prefix)}</span> '
                        if primary_prefix
                        else ""
                    )
                    out.append(
                        f'<li><span class="label">Key question:</span> {tag}{escape(primary_text)}</li>'
                    )
                for sec_text, sec_prefix in secondary:
                    tag = f'<span class="tag">{escape(sec_prefix)}</span> ' if sec_prefix else ""
                    out.append(f'<li class="muted">Also open: {tag}{escape(sec_text)}</li>')
                out.append("</ul>")

            items = watch_items(futures)
            if items:
                out.append("<ul>")
                for item in items:
                    out.append(
                        f'<li><span class="label">Watch for:</span> '
                        f'<span class="muted">{escape(item)}</span></li>'
                    )
                out.append("</ul>")

        causal = situation.get("causal_structure", {})
        if causal:
            out.append("<h3>Causal structure</h3>")
            out.extend(
                self._definition_list(
                    [
                        ("Forces", causal.get("forces"), True),
                        ("Constraints", causal.get("constraints"), True),
                        ("Dependencies", causal.get("dependencies"), True),
                    ]
                )
            )

        gaps = situation.get("information_gaps", [])
        if gaps:
            out.append("<h3>Information gaps</h3>")
            out.append("<ul>")
            for gap in gaps:
                missing = escape(str(gap.get("what_is_missing", "") or ""))
                details = []
                if gap.get("why_it_matters"):
                    details.append(f"Why it matters: {escape(str(gap['why_it_matters']))}")
                if gap.get("why_missing"):
                    details.append(f"Why missing: {escape(str(gap['why_missing']))}")
                if gap.get("feed_recommendation"):
                    details.append(f"Suggested source: {escape(str(gap['feed_recommendation']))}")
                detail_html = ""
                if details:
                    items_html = "".join(f'<li class="muted">{d}</li>' for d in details)
                    detail_html = f"<ul>{items_html}</ul>"
                out.append(f'<li><span class="gap">GAP</span>: {missing}{detail_html}</li>')
            out.append("</ul>")

        out.append("</section>")
        return out

    def _meta_fractures(self, doc: BriefDocument) -> list[str]:
        if not doc.meta_fractures:
            return []
        out = [
            "<h2>Meta-fractures</h2>",
            '<p class="section-note">Underlying frame conflicts that surface across situations.</p>',
        ]
        for mf in doc.meta_fractures:
            out.append(f"<h3>{escape(str(mf.get('name', '(unnamed)')))}</h3>")
            if mf.get("description"):
                out.append(f"<p>{escape(str(mf['description']))}</p>")
            indices = mf.get("situation_indices", [])
            if indices:
                labels = ", ".join(f"Situation {int(i) + 1}" for i in indices)
                out.append(f'<p class="tag">Appears in: {escape(labels)}</p>')
            if mf.get("shared_point"):
                out.append(
                    f'<p><span class="label">Shared point:</span> '
                    f'<span class="muted">{escape(str(mf["shared_point"]))}</span></p>'
                )
        return out

    def _thin_coverage(self, doc: BriefDocument) -> list[str]:
        if not doc.thin_coverage:
            return []
        out = [
            "<h2>Thin coverage</h2>",
            '<p class="section-note">Topics with 1-2 articles. Listed but not fully analyzed.</p>',
            "<ul>",
        ]
        for item in doc.thin_coverage:
            title = escape(str(item.get("title", "Unknown topic")))
            count = escape(str(item.get("article_count", 0)))
            sources = escape(", ".join(str(s) for s in item.get("sources", [])))
            note = item.get("note", "")
            note_html = f'<ul><li class="muted">{escape(str(note))}</li></ul>' if note else ""
            out.append(
                f'<li><span class="label">{title}</span> '
                f'<span class="tag">{count} article(s) | {sources}</span>{note_html}</li>'
            )
        out.append("</ul>")
        return out

    @staticmethod
    def _definition_list(rows: list[tuple[str, object, bool]]) -> list[str]:
        """
        Render ``(label, value, strip_citations)`` rows as a list, skipping
        empty values. Returns an empty list when nothing survives.
        """
        rendered = []
        for label, value, strip in rows:
            if not value:
                continue
            text = str(value)
            if strip:
                text = clean_citations(text)
            rendered.append(f'<li><span class="label">{escape(label)}:</span> {escape(text)}</li>')
        if not rendered:
            return []
        return ["<ul>", *rendered, "</ul>"]
