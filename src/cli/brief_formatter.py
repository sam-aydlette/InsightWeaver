"""
Brief Report Terminal Formatter
Renders situation-based synthesis output for terminal display.
"""

import re
from typing import Any

from ..utils.base_formatter import BaseTerminalFormatter
from .colors import accent, header, muted, warning


def clean_citations(text: str) -> str:
    """Convert ^[N,M] citation markers to [N,M] for terminal display."""
    if not text:
        return text
    return re.sub(r"\^\[([0-9,\s]+)\]", r"[\1]", text)


def _decision_summary(metadata: dict) -> list[dict]:
    """Pull the decision-routing summary out of synthesis metadata."""
    routing = metadata.get("decision_routing")
    return routing if isinstance(routing, list) else []


_DIRECTION_GLYPH = {
    "supports": "+",
    "complicates": "-",
    "neutral": "~",
}


def _prediction_check_line(check: dict | None) -> str:
    """One-line transparency summary of the pre-synthesis prediction check."""
    if not isinstance(check, dict):
        return ""
    checked = check.get("checked", 0)
    if not checked and not check.get("expired"):
        return ""
    triggered = check.get("triggered", 0)
    contradicted = check.get("contradicted", 0)
    still_open = check.get("still_open", 0)
    expired = check.get("expired", 0)
    return (
        f"Prediction check: {checked} open observables graded -- "
        f"{triggered} triggered, {contradicted} contradicted, "
        f"{still_open} still open, {expired} expired. "
        f"See 'predictions track-record'."
    )


def _watch_items(futures: dict) -> list[str]:
    """Extract what_to_watch observables. Handles the list-of-objects shape
    and the legacy single-string shape."""
    watch = futures.get("what_to_watch")
    if isinstance(watch, str):
        return [watch] if watch.strip() else []
    if not isinstance(watch, list):
        return []
    items: list[str] = []
    for entry in watch:
        if isinstance(entry, str) and entry.strip():
            items.append(entry.strip())
        elif isinstance(entry, dict):
            observable = (entry.get("observable") or "").strip()
            trigger = (entry.get("trigger_condition") or "").strip()
            if observable and trigger:
                items.append(f"{observable} -- {trigger}")
            elif observable:
                items.append(observable)
    return items


def _question_lines(
    futures: dict,
) -> tuple[str, str, list[tuple[str, str]]]:
    """
    Extract primary question text + identity prefix and secondary lines from
    a ``where_this_goes`` block. Returns ``(primary_text, primary_prefix,
    secondary)`` where each secondary is ``(text, prefix)``. Prefix is empty
    when a question has no identity metadata or is appearing for the first
    time -- accumulation context is only shown for repeat appearances.
    """
    uq = futures.get("unresolved_questions")
    if not isinstance(uq, dict):
        legacy = futures.get("unresolved_question")
        if isinstance(legacy, str):
            return legacy, "", []
        return "", "", []

    def _split(entry: Any) -> tuple[str, str]:
        if isinstance(entry, str):
            return entry, ""
        if not isinstance(entry, dict):
            return "", ""
        text = entry.get("text", "")
        qid = entry.get("question_id")
        appearance = entry.get("appearance_count")
        if qid is None or appearance is None:
            return text, ""
        if appearance <= 1:
            return text, f"Q{qid} (new)"
        first = entry.get("first_asked_at", "")
        first_date = first.split("T", 1)[0] if isinstance(first, str) else ""
        return text, f"Q{qid} (run {appearance}, asked {first_date})"

    primary_text, primary_prefix = _split(uq.get("primary"))
    secondary: list[tuple[str, str]] = []
    for entry in uq.get("secondary") or []:
        text, prefix = _split(entry)
        if text:
            secondary.append((text, prefix))
    return primary_text, primary_prefix, secondary


class BriefFormatter(BaseTerminalFormatter):
    """Format situation-based intelligence briefs for terminal display."""

    def __init__(self, max_width: int = 80):
        super().__init__(max_width)

    def format_report(self, report_data: dict[str, Any]) -> str:
        """Format a complete briefing for terminal output."""
        synthesis_data = report_data.get("synthesis_data", {})
        situations = synthesis_data.get("situations", [])
        thin_coverage = synthesis_data.get("thin_coverage", [])
        metadata = synthesis_data.get("metadata", {})

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

        check_line = _prediction_check_line(metadata.get("prediction_check"))
        if check_line:
            lines.append(muted(check_line))
        lines.append("")

        # Your decisions -- what today's coverage moved
        decisions = _decision_summary(metadata)
        if decisions:
            lines.append(header("YOUR DECISIONS"))
            lines.append(muted("What today's coverage moved. See 'decisions show <id>'."))
            lines.append("")
            for entry in decisions:
                lines.append(f"  {accent(entry.get('decision', '(decision)'))}")
                for factor in entry.get("factors", []):
                    direction = factor.get("direction", "neutral")
                    glyph = _DIRECTION_GLYPH.get(direction, "~")
                    name = factor.get("name", "(factor)")
                    lines.append(f"    [{glyph}] {name} {muted(f'({direction})')}")
            lines.append("")

        # Situations
        if situations:
            for i, situation in enumerate(situations, 1):
                lines.append(self._format_situation(situation, i))
                lines.append("")
        else:
            lines.append(muted("No situations met the analysis threshold."))
            lines.append("")

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

    def _format_situation(self, situation: dict, index: int) -> str:
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

            primary_text, primary_prefix, secondary = _question_lines(futures)
            if primary_text:
                tag = f"{muted(primary_prefix)} " if primary_prefix else ""
                lines.append(f"    Key question: {tag}{primary_text}")
            for sec_text, sec_prefix in secondary:
                tag = f"{muted(sec_prefix)} " if sec_prefix else ""
                lines.append(f"      Also open: {tag}{muted(sec_text)}")

            for item in _watch_items(futures):
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

    def format_one_line_summary(self, report_data: dict[str, Any]) -> str:
        """One-line summary for the command refresher."""
        synthesis_data = report_data.get("synthesis_data", {})
        situations = synthesis_data.get("situations", [])
        articles = synthesis_data.get("metadata", {}).get("articles_analyzed", 0)

        return f"BRIEF: {articles} articles, {len(situations)} situations analyzed"

    def format_markdown(self, report_data: dict[str, Any]) -> str:
        """Render the brief as markdown for archival via --save."""
        synthesis_data = report_data.get("synthesis_data", {})
        situations = synthesis_data.get("situations", [])
        thin_coverage = synthesis_data.get("thin_coverage", [])
        metadata = synthesis_data.get("metadata", {})

        lines: list[str] = ["# Intelligence Brief", ""]

        articles = metadata.get("articles_analyzed", 0)
        clusters_analyzed = metadata.get("clusters_analyzed", 0)
        clusters_thin = metadata.get("clusters_thin", 0)
        threshold = metadata.get("analysis_threshold", "3+ articles")
        lines.append(
            f"_Articles: {articles} | Situations: {clusters_analyzed} analyzed, "
            f"{clusters_thin} thin coverage | Threshold: {threshold}_"
        )
        check_line = _prediction_check_line(metadata.get("prediction_check"))
        if check_line:
            lines.append("")
            lines.append(f"_{check_line}_")
        lines.append("")

        decisions = _decision_summary(metadata)
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
                lines.extend(self._format_situation_markdown(situation, i))
                lines.append("")
        else:
            lines.append("_No situations met the analysis threshold._")
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

    def _format_situation_markdown(self, situation: dict, index: int) -> list[str]:
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

            primary_text, primary_prefix, secondary = _question_lines(futures)
            if primary_text:
                prefix_part = f"_{primary_prefix}_ " if primary_prefix else ""
                lines.append(f"- **Key question:** {prefix_part}{primary_text}")
            for sec_text, sec_prefix in secondary:
                prefix_part = f"_{sec_prefix}_ " if sec_prefix else ""
                lines.append(f"  - Also open: {prefix_part}{sec_text}")

            for item in _watch_items(futures):
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
