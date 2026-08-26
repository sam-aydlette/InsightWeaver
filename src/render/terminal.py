"""
Terminal renderer.

The output of :meth:`TerminalRenderer.render` is the brief as InsightWeaver has
always printed it -- this is a move of the former ``BriefFormatter.format_report``,
not a rewrite. It is byte-for-byte compatible with the pre-split output for the
same synthesis payload, which is what makes replaying a stored run verifiable.
"""

from __future__ import annotations

from ..utils.base_formatter import BaseTerminalFormatter
from ..utils.colors import accent, header, muted, warning
from ._text import (
    ACTIVITY_NOTE,
    DIRECTION_GLYPH,
    activity_footnote,
    activity_sentence,
    clean_citations,
    decision_summary,
    institutional_activity,
    prediction_check_line,
    question_lines,
    split_activity,
    standing_agenda,
    standing_agenda_movement,
    standing_agenda_no_movement,
    standing_agenda_provenance,
    standing_agenda_status,
    watch_items,
)
from .document import BriefDocument

__all__ = ["TerminalRenderer", "clean_citations"]


class TerminalRenderer(BaseTerminalFormatter):
    """Render a :class:`BriefDocument` for terminal display."""

    def __init__(self, max_width: int = 80) -> None:
        super().__init__(max_width)

    def render(self, doc: BriefDocument) -> str:
        """Format a complete briefing for terminal output."""
        situations = doc.situations
        thin_coverage = doc.thin_coverage
        meta_fractures = doc.meta_fractures
        metadata = doc.metadata

        lines = []

        # Header
        lines.append("")
        lines.append(header("=" * self.max_width))
        lines.append(header("INTELLIGENCE BRIEF"))
        lines.append(header("=" * self.max_width))
        lines.append("")

        # Metadata
        articles = metadata.get("articles_analyzed", 0)
        clusters_analyzed = metadata.get("clusters_analyzed", 0)
        clusters_thin = metadata.get("clusters_thin", 0)
        threshold = metadata.get("analysis_threshold", "3+ articles")

        lines.append(
            muted(
                f"Articles: {articles} | "
                f"Situations: {clusters_analyzed} analyzed, {clusters_thin} thin coverage | "
                f"Threshold: {threshold}"
            )
        )

        check_line = prediction_check_line(metadata.get("prediction_check"))
        if check_line:
            lines.append(muted(check_line))
        lines.append("")

        # Your decisions -- what today's coverage moved
        decisions = decision_summary(metadata)
        if decisions:
            lines.append(header("YOUR DECISIONS"))
            lines.append(muted("What today's coverage moved. See 'decisions show <id>'."))
            lines.append("")
            for entry in decisions:
                lines.append(f"  {accent(entry.get('decision', '(decision)'))}")
                for factor in entry.get("factors", []):
                    direction = factor.get("direction", "neutral")
                    glyph = DIRECTION_GLYPH.get(direction, "~")
                    name = factor.get("name", "(factor)")
                    lines.append(f"    [{glyph}] {name} {muted(f'({direction})')}")
            lines.append("")

        # Standing agenda -- what this beat declared it is watching.
        lines.extend(self._render_standing_agenda(doc))

        # Situations
        if situations:
            for i, situation in enumerate(situations, 1):
                lines.append(self._render_situation(situation, i))
                lines.append("")
        else:
            lines.append(muted("No situations met the analysis threshold."))
            lines.append("")

        # Meta-fractures across situations (Stage 6).
        if meta_fractures:
            lines.append(header("-" * self.max_width))
            lines.append(header("META-FRACTURES"))
            lines.append(muted("Underlying frame conflicts that surface across situations."))
            lines.append(header("-" * self.max_width))
            lines.append("")
            for mf in meta_fractures:
                lines.append(accent(f"  {mf.get('name', '(unnamed)')}"))
                if mf.get("description"):
                    lines.append(f"    {mf['description']}")
                indices = mf.get("situation_indices", [])
                if indices:
                    sit_labels = ", ".join(f"Situation {i + 1}" for i in indices)
                    lines.append(muted(f"    Appears in: {sit_labels}"))
                if mf.get("shared_point"):
                    lines.append(f"    Shared point: {muted(mf['shared_point'])}")
                lines.append("")

        # Institutional activity -- what the beat's declared institutions did
        # this run against what they usually do.
        lines.extend(self._render_institutional_activity(metadata))

        # Thin coverage
        if thin_coverage:
            lines.append(header("-" * self.max_width))
            lines.append(header("THIN COVERAGE"))
            lines.append(muted("Topics with 1-2 articles. Listed but not fully analyzed."))
            lines.append(header("-" * self.max_width))
            lines.append("")

            for item in thin_coverage:
                title = item.get("title", "Unknown topic")
                count = item.get("article_count", 0)
                sources = ", ".join(item.get("sources", []))
                note = item.get("note", "")

                lines.append(f"  {accent(title)}")
                lines.append(f"    {muted(f'{count} article(s) | {sources}')}")
                if note:
                    lines.append(f"    {note}")
                lines.append("")

        lines.append(header("=" * self.max_width))

        return "\n".join(lines)

    def _render_institutional_activity(self, metadata: dict) -> list[str]:
        """
        Format the institutional activity section, or nothing at all.

        Two blocks, and both matter. The first is what moved. The second is the
        entities that have been active before and are steady or silent today --
        quieter, but present, because an office going quiet is information and
        a section that only ever showed increases would read as a scoreboard.
        """
        block = institutional_activity(metadata)
        moved, steady = split_activity(block)
        if not moved and not steady:
            return []

        lines = [
            header("-" * self.max_width),
            header("INSTITUTIONAL ACTIVITY"),
            muted(ACTIVITY_NOTE),
            header("-" * self.max_width),
            "",
        ]
        for entry in moved:
            lines.append(f"  {activity_sentence(entry)}")
        if moved and steady:
            lines.append("")
        for entry in steady:
            lines.append(muted(f"  {activity_sentence(entry)}"))

        footnote = activity_footnote(block)
        if footnote:
            lines.append("")
            lines.append(muted(f"  {footnote}"))
        lines.append("")
        return lines

    def _render_standing_agenda(self, doc: BriefDocument) -> list[str]:
        """
        The beat's declared agenda, every item of it.

        Each entry is rendered whether or not it moved. There is deliberately
        no "skip the quiet ones" branch here: a standing question that vanishes
        on a quiet day is the exact failure this section exists to prevent, so
        an unmoved question gets a NO MOVEMENT label and a sentence saying so.
        """
        agenda = standing_agenda(doc.metadata)
        if not agenda:
            return []

        lines = [
            header("STANDING AGENDA"),
            muted(
                "What this beat declared it is watching. Unmoved items are reported, not dropped."
            ),
            "",
        ]
        for entry in agenda:
            status = standing_agenda_status(entry)
            label = accent(f"[{status}]") if entry.get("moved") else warning(f"[{status}]")
            lines.append(f"  {label} {entry.get('text', '(question)')}")
            lines.append(f"    {muted(standing_agenda_provenance(entry))}")

            movement = standing_agenda_movement(entry)
            if movement:
                for item in movement:
                    lines.append(f"    Moved in: {item}")
            else:
                lines.append(f"    {muted(standing_agenda_no_movement(entry))}")

            for observable in entry.get("watching") or []:
                lines.append(f"    Watching for: {muted(str(observable))}")
            lines.append("")

        return lines

    def _render_situation(self, situation: dict, index: int) -> str:
        """Format a single situation for terminal display."""
        lines = []

        title = clean_citations(situation.get("title", "Untitled situation"))
        lines.append(header(f"SITUATION {index}: {title}"))
        lines.append(header("-" * self.max_width))

        # Narrative
        narrative = situation.get("narrative", "")
        if narrative:
            lines.append("")
            for paragraph in clean_citations(narrative).split("\n\n"):
                lines.append(self.wrap_text(paragraph.strip()))
                lines.append("")

        # Actors
        actors = situation.get("actors", [])
        if actors:
            lines.append(accent("  ACTORS:"))
            for actor in actors:
                name = actor.get("name", "Unknown")
                role = actor.get("role", "")
                interests = actor.get("interests", "")
                status = actor.get("epistemic_status", "")
                status_tag = f" [{status}]" if status else ""

                lines.append(f"    {name}{muted(status_tag)}")
                if role:
                    lines.append(f"      Role: {role}")
                if interests:
                    lines.append(f"      Interests: {interests}")
            lines.append("")

        # Power dynamics
        power = situation.get("power_dynamics", {})
        if power:
            lines.append(accent("  POWER DYNAMICS:"))
            if power.get("who_benefits"):
                lines.append(f"    Benefits: {clean_citations(power['who_benefits'])}")
            if power.get("who_is_harmed"):
                lines.append(f"    Harmed: {clean_citations(power['who_is_harmed'])}")
            if power.get("who_decides"):
                lines.append(f"    Decides: {clean_citations(power['who_decides'])}")
            lines.append("")

        # Coverage frame / narrative layers
        frame = situation.get("coverage_frame", {})
        if frame:
            lines.append(accent("  WHAT THE COVERAGE MAKES VISIBLE AND INVISIBLE:"))
            if frame.get("narrative_layers"):
                lines.append(f"    Narratives: {frame['narrative_layers']}")
            elif frame.get("dominant_frame"):
                # Backward compat with old schema
                lines.append(f"    Frame: {frame['dominant_frame']}")
            if frame.get("fractures"):
                lines.append(f"    Fractures: {frame['fractures']}")
            if frame.get("bridges"):
                lines.append(f"    Bridges: {muted(frame['bridges'])}")
            if frame.get("structural_absences"):
                lines.append(f"    Hard to see: {muted(frame['structural_absences'])}")
            if frame.get("assumed_premise"):
                lines.append(f"    Assumes: {muted(frame['assumed_premise'])}")
            lines.append("")

        # Where this goes
        futures = situation.get("where_this_goes", {})
        if futures:
            lines.append(accent("  WHERE THIS GOES:"))
            if futures.get("branching_paths"):
                lines.append(f"    Paths: {clean_citations(futures['branching_paths'])}")

            primary_text, primary_prefix, secondary = question_lines(futures)
            if primary_text:
                tag = f"{muted(primary_prefix)} " if primary_prefix else ""
                lines.append(f"    Key question: {tag}{primary_text}")
            for sec_text, sec_prefix in secondary:
                tag = f"{muted(sec_prefix)} " if sec_prefix else ""
                lines.append(f"      Also open: {tag}{muted(sec_text)}")

            for item in watch_items(futures):
                lines.append(f"    Watch for: {muted(item)}")
            lines.append("")

        # Causal structure (backward compat -- may not be present in new schema)
        causal = situation.get("causal_structure", {})
        if causal:
            lines.append(accent("  CAUSAL STRUCTURE:"))
            if causal.get("forces"):
                lines.append(f"    Forces: {clean_citations(causal['forces'])}")
            if causal.get("constraints"):
                lines.append(f"    Constraints: {clean_citations(causal['constraints'])}")
            if causal.get("dependencies"):
                lines.append(f"    Dependencies: {clean_citations(causal['dependencies'])}")
            lines.append("")

        # Information gaps
        gaps = situation.get("information_gaps", [])
        if gaps:
            lines.append(accent("  INFORMATION GAPS:"))
            for gap in gaps:
                missing = gap.get("what_is_missing", "")
                why = gap.get("why_it_matters", "")
                why_missing = gap.get("why_missing", "")
                feed = gap.get("feed_recommendation", "")

                lines.append(f"    {warning('GAP')}: {missing}")
                if why:
                    lines.append(f"      Why it matters: {muted(why)}")
                if why_missing:
                    lines.append(f"      Why missing: {muted(why_missing)}")
                if feed:
                    lines.append(f"      Suggested source: {muted(feed)}")
            lines.append("")

        return "\n".join(lines)

    def render_compact(self, doc: BriefDocument) -> str:
        """
        Situation titles only, for scripts and automation (``--quiet``).

        Emitted as one string rather than a sequence of ``click.echo`` calls so
        that there is a single place that decides this layout.
        """
        lines: list[str] = [""]

        if doc.situations:
            lines.append(header("Situations analyzed:"))
            for i, situation in enumerate(doc.situations, 1):
                title = clean_citations(situation.get("title", "Untitled"))
                lines.append(f"  {accent(f'{i}.')} {title}")

        if doc.thin_coverage:
            lines.append(muted(f"\n+ {len(doc.thin_coverage)} topics with thin coverage"))

        lines.append(
            muted(
                f"\nArticles: {doc.articles_analyzed} | "
                f"Clusters: {doc.metadata.get('clusters_total', 0)}"
            )
        )
        return "\n".join(lines)

    def render_one_line_summary(self, doc: BriefDocument) -> str:
        """One-line summary for the command refresher."""
        return (
            f"BRIEF: {doc.metadata.get('articles_analyzed', 0)} articles, "
            f"{len(doc.situations)} situations analyzed"
        )
