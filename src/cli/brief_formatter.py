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

        # Coverage frame
        frame = situation.get("coverage_frame", {})
        if frame:
            lines.append(accent("  COVERAGE FRAME:"))
            if frame.get("dominant_frame"):
                lines.append(f"    Frame: {frame['dominant_frame']}")
            if frame.get("assumed_premise"):
                lines.append(f"    Assumes: {muted(frame['assumed_premise'])}")
            if frame.get("de_emphasized"):
                lines.append(f"    De-emphasized: {muted(frame['de_emphasized'])}")
            lines.append("")

        # Causal structure
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
                feed = gap.get("feed_recommendation", "")

                lines.append(f"    {warning('GAP')}: {missing}")
                if why:
                    lines.append(f"      Why it matters: {muted(why)}")
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
