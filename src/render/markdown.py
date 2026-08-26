"""
Markdown renderer -- the archival format behind ``brief --save PATH``.

A move of the former ``BriefFormatter.format_markdown``, unchanged in output.
"""

from __future__ import annotations

from ._text import (
    clean_citations,
    decision_summary,
    prediction_check_line,
    question_lines,
    watch_items,
)
from .document import BriefDocument

__all__ = ["MarkdownRenderer"]


class MarkdownRenderer:
    """Render a :class:`BriefDocument` as markdown for archival."""

    def render(self, doc: BriefDocument) -> str:
        situations = doc.situations
        thin_coverage = doc.thin_coverage
        meta_fractures = doc.meta_fractures
        metadata = doc.metadata

        lines: list[str] = ["# Intelligence Brief", ""]

        articles = metadata.get("articles_analyzed", 0)
        clusters_analyzed = metadata.get("clusters_analyzed", 0)
        clusters_thin = metadata.get("clusters_thin", 0)
        threshold = metadata.get("analysis_threshold", "3+ articles")
        lines.append(
            f"_Articles: {articles} | Situations: {clusters_analyzed} analyzed, "
            f"{clusters_thin} thin coverage | Threshold: {threshold}_"
        )
        check_line = prediction_check_line(metadata.get("prediction_check"))
        if check_line:
            lines.append("")
            lines.append(f"_{check_line}_")
        lines.append("")

        decisions = decision_summary(metadata)
        if decisions:
            lines.append("## Your decisions")
            lines.append("")
            lines.append("_What today's coverage moved._")
            lines.append("")
            for entry in decisions:
                lines.append(f"### {entry.get('decision', '(decision)')}")
                for factor in entry.get("factors", []):
                    direction = factor.get("direction", "neutral")
                    name = factor.get("name", "(factor)")
                    lines.append(f"- **{name}** — {direction}")
                lines.append("")

        if situations:
            for i, situation in enumerate(situations, 1):
                lines.extend(self._render_situation(situation, i))
                lines.append("")
        else:
            lines.append("_No situations met the analysis threshold._")
            lines.append("")

        if meta_fractures:
            lines.append("## Meta-fractures")
            lines.append("")
            lines.append("_Underlying frame conflicts that surface across situations._")
            lines.append("")
            for mf in meta_fractures:
                lines.append(f"### {mf.get('name', '(unnamed)')}")
                if mf.get("description"):
                    lines.append("")
                    lines.append(mf["description"])
                indices = mf.get("situation_indices", [])
                if indices:
                    sit_labels = ", ".join(f"Situation {i + 1}" for i in indices)
                    lines.append("")
                    lines.append(f"_Appears in: {sit_labels}_")
                if mf.get("shared_point"):
                    lines.append("")
                    lines.append(f"**Shared point:** {mf['shared_point']}")
                lines.append("")

        if thin_coverage:
            lines.append("## Thin coverage")
            lines.append("")
            lines.append("_Topics with 1-2 articles. Listed but not fully analyzed._")
            lines.append("")
            for item in thin_coverage:
                title = item.get("title", "Unknown topic")
                count = item.get("article_count", 0)
                sources = ", ".join(item.get("sources", []))
                note = item.get("note", "")
                lines.append(f"- **{title}** — {count} article(s) | {sources}")
                if note:
                    lines.append(f"  - {note}")
            lines.append("")

        return "\n".join(lines)

    def _render_situation(self, situation: dict, index: int) -> list[str]:
        """Render a single situation as markdown."""
        lines: list[str] = []
        title = clean_citations(situation.get("title", "Untitled situation"))
        lines.append(f"## Situation {index}: {title}")
        lines.append("")

        narrative = situation.get("narrative", "")
        if narrative:
            for paragraph in clean_citations(narrative).split("\n\n"):
                lines.append(paragraph.strip())
                lines.append("")

        actors = situation.get("actors", [])
        if actors:
            lines.append("### Actors")
            lines.append("")
            for actor in actors:
                name = actor.get("name", "Unknown")
                status = actor.get("epistemic_status", "")
                status_tag = f" _[{status}]_" if status else ""
                lines.append(f"- **{name}**{status_tag}")
                if actor.get("role"):
                    lines.append(f"  - Role: {actor['role']}")
                if actor.get("interests"):
                    lines.append(f"  - Interests: {actor['interests']}")
            lines.append("")

        power = situation.get("power_dynamics", {})
        if power:
            lines.append("### Power dynamics")
            lines.append("")
            if power.get("who_benefits"):
                lines.append(f"- **Benefits:** {clean_citations(power['who_benefits'])}")
            if power.get("who_is_harmed"):
                lines.append(f"- **Harmed:** {clean_citations(power['who_is_harmed'])}")
            if power.get("who_decides"):
                lines.append(f"- **Decides:** {clean_citations(power['who_decides'])}")
            lines.append("")

        frame = situation.get("coverage_frame", {})
        if frame:
            lines.append("### What the coverage makes visible and invisible")
            lines.append("")
            if frame.get("narrative_layers"):
                lines.append(f"- **Narratives:** {frame['narrative_layers']}")
            elif frame.get("dominant_frame"):
                lines.append(f"- **Frame:** {frame['dominant_frame']}")
            if frame.get("fractures"):
                lines.append(f"- **Fractures:** {frame['fractures']}")
            if frame.get("bridges"):
                lines.append(f"- **Bridges:** {frame['bridges']}")
            if frame.get("structural_absences"):
                lines.append(f"- **Hard to see:** {frame['structural_absences']}")
            if frame.get("assumed_premise"):
                lines.append(f"- **Assumes:** {frame['assumed_premise']}")
            lines.append("")

        futures = situation.get("where_this_goes", {})
        if futures:
            lines.append("### Where this goes")
            lines.append("")
            if futures.get("branching_paths"):
                lines.append(f"- **Paths:** {clean_citations(futures['branching_paths'])}")

            primary_text, primary_prefix, secondary = question_lines(futures)
            if primary_text:
                prefix_part = f"_{primary_prefix}_ " if primary_prefix else ""
                lines.append(f"- **Key question:** {prefix_part}{primary_text}")
            for sec_text, sec_prefix in secondary:
                prefix_part = f"_{sec_prefix}_ " if sec_prefix else ""
                lines.append(f"  - Also open: {prefix_part}{sec_text}")

            for item in watch_items(futures):
                lines.append(f"- **Watch for:** {item}")
            lines.append("")

        causal = situation.get("causal_structure", {})
        if causal:
            lines.append("### Causal structure")
            lines.append("")
            if causal.get("forces"):
                lines.append(f"- **Forces:** {clean_citations(causal['forces'])}")
            if causal.get("constraints"):
                lines.append(f"- **Constraints:** {clean_citations(causal['constraints'])}")
            if causal.get("dependencies"):
                lines.append(f"- **Dependencies:** {clean_citations(causal['dependencies'])}")
            lines.append("")

        gaps = situation.get("information_gaps", [])
        if gaps:
            lines.append("### Information gaps")
            lines.append("")
            for gap in gaps:
                missing = gap.get("what_is_missing", "")
                lines.append(f"- **Gap:** {missing}")
                if gap.get("why_it_matters"):
                    lines.append(f"  - Why it matters: {gap['why_it_matters']}")
                if gap.get("why_missing"):
                    lines.append(f"  - Why missing: {gap['why_missing']}")
                if gap.get("feed_recommendation"):
                    lines.append(f"  - Suggested source: {gap['feed_recommendation']}")
            lines.append("")

        return lines
