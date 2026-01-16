"""
Brief Report Terminal Formatter
Format intelligence reports for terminal display
"""

import re
from typing import Any

from ..utils.base_formatter import BaseTerminalFormatter
from .colors import colorize_priority, header, muted


def clean_citations(text: str) -> str:
    """
    Convert citation markers from ^[N,M] to [N,M] for cleaner terminal display.

    Args:
        text: Text containing citation markers

    Returns:
        Text with cleaned citation format
    """
    if not text:
        return text
    # Convert ^[N] or ^[N,M,O] to [N] or [N,M,O]
    return re.sub(r"\^\[([0-9,\s]+)\]", r"[\1]", text)


class BriefFormatter(BaseTerminalFormatter):
    """Format intelligence brief reports for terminal display"""

    def __init__(self, max_width: int = 80):
        super().__init__(max_width)

    def format_report(self, report_data: dict[str, Any]) -> str:
        """
        Format complete intelligence report for terminal

        Args:
            report_data: Report data from NewsletterSystem

        Returns:
            Formatted report string
        """
        lines = []

        # Header
        lines.append("\n" + header("=" * self.max_width))
        lines.append(header("INTELLIGENCE BRIEF"))
        lines.append(header("=" * self.max_width))

        # Time window
        start = report_data.get("start_date")
        end = report_data.get("end_date")
        duration = report_data.get("duration_hours", 0)

        if start and end:
            lines.append(
                muted(
                    f"\nTime Window: {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')} ({duration:.1f}h)"
                )
            )

        lines.append(muted(f"Articles Analyzed: {report_data.get('articles_analyzed', 0)}"))
        lines.append(muted(f"Report Type: {report_data.get('report_type', 'custom').upper()}"))
        lines.append("")

        # Executive Summary
        exec_summary = report_data.get("executive_summary", "")
        if (
            exec_summary
            and isinstance(exec_summary, str)
            and exec_summary != "No articles found in the specified time window."
        ):
            lines.append(header("-" * self.max_width))
            lines.append(header("EXECUTIVE SUMMARY"))
            lines.append(header("-" * self.max_width))
            lines.append("")
            lines.append(self.wrap_text(clean_citations(exec_summary)))
            lines.append("")

        # Synthesis Data
        synthesis_data = report_data.get("synthesis_data", {})

        if synthesis_data:
            # Bottom Line - can be dict with 'summary' key or string
            bottom_line_data = synthesis_data.get("bottom_line", "")
            if isinstance(bottom_line_data, dict):
                bottom_line = bottom_line_data.get("summary", "")
            else:
                bottom_line = bottom_line_data

            if bottom_line and isinstance(bottom_line, str):
                lines.append(header("-" * self.max_width))
                lines.append(header("BOTTOM LINE"))
                lines.append(header("-" * self.max_width))
                lines.append("")
                lines.append(self.wrap_text(clean_citations(bottom_line)))
                lines.append("")

            # Trends and Patterns
            lines.extend(self._format_trends(synthesis_data.get("trends_and_patterns", [])))

            # Priority Events
            lines.extend(self._format_events(synthesis_data.get("priority_events", [])))

            # Predictions and Scenarios
            lines.extend(self._format_predictions(synthesis_data.get("predictions_scenarios", [])))

        # Footer
        lines.append(header("=" * self.max_width))
        lines.append(header("End of Intelligence Brief"))
        lines.append(header("=" * self.max_width))
        lines.append("")

        return "\n".join(lines)

    def _format_trends(self, trends: list) -> list[str]:
        """Format trends and patterns section"""
        if not trends or not isinstance(trends, list):
            return []

        lines = [
            header("-" * self.max_width),
            header("KEY TRENDS & PATTERNS"),
            header("-" * self.max_width),
            "",
        ]

        for i, trend in enumerate(trends, 1):
            if not isinstance(trend, dict):
                continue

            # Trend header
            trend_title = trend.get("trend", "Unknown Trend")
            if isinstance(trend_title, str):
                lines.append(f"{i}. {clean_citations(trend_title)}")
                lines.append("")

            # Description
            description = trend.get("description", "")
            if description and isinstance(description, str):
                lines.append(self.wrap_text(clean_citations(description), indent=3))
                lines.append("")

            # Evidence
            evidence = trend.get("evidence", [])
            if evidence and isinstance(evidence, list):
                lines.append("   Evidence:")
                for item in evidence:
                    if isinstance(item, str):
                        lines.append(
                            self.wrap_text(
                                f"* {clean_citations(item)}", indent=5, subsequent_indent=7
                            )
                        )
                lines.append("")

            # Significance
            significance = trend.get("significance", "")
            if significance and isinstance(significance, str):
                lines.append(
                    self.wrap_text(f"Significance: {clean_citations(significance)}", indent=3)
                )
                lines.append("")

        return lines

    def _format_events(self, events: list) -> list[str]:
        """Format priority events section"""
        if not events or not isinstance(events, list):
            return []

        lines = [
            header("-" * self.max_width),
            header("PRIORITY EVENTS"),
            header("-" * self.max_width),
            "",
        ]

        for i, event in enumerate(events, 1):
            if not isinstance(event, dict):
                continue

            # Event header with colorized priority
            event_title = event.get("event", "Unknown Event")
            priority = event.get("priority", "MEDIUM")
            if isinstance(event_title, str) and isinstance(priority, str):
                lines.append(f"{i}. {colorize_priority(priority)} {clean_citations(event_title)}")
                lines.append("")

            # Summary
            summary = event.get("summary", "")
            if summary and isinstance(summary, str):
                lines.append(self.wrap_text(clean_citations(summary), indent=3))
                lines.append("")

            # Why it matters
            why_matters = event.get("why_it_matters", "")
            if why_matters and isinstance(why_matters, str):
                lines.append(
                    self.wrap_text(f"Why it matters: {clean_citations(why_matters)}", indent=3)
                )
                lines.append("")

            # Context
            context = event.get("context", "")
            if context and isinstance(context, str):
                lines.append(self.wrap_text(f"Context: {clean_citations(context)}", indent=3))
                lines.append("")

        return lines

    def _format_predictions(self, predictions: list) -> list[str]:
        """Format predictions and scenarios section"""
        if not predictions or not isinstance(predictions, list):
            return []

        lines = [
            header("-" * self.max_width),
            header("PREDICTIONS & SCENARIOS"),
            header("-" * self.max_width),
            "",
        ]

        for i, prediction in enumerate(predictions, 1):
            if not isinstance(prediction, dict):
                continue

            # Prediction header
            pred_title = prediction.get("scenario", "Unknown Scenario")
            timeframe = prediction.get("timeframe", "Unknown")
            if isinstance(pred_title, str) and isinstance(timeframe, str):
                lines.append(f"{i}. {clean_citations(pred_title)} ({timeframe})")
                lines.append("")

            # Prediction text
            pred_text = prediction.get("prediction", "")
            if pred_text and isinstance(pred_text, str):
                lines.append(self.wrap_text(clean_citations(pred_text), indent=3))
                lines.append("")

            # Likelihood
            likelihood = prediction.get("likelihood", "")
            if likelihood and isinstance(likelihood, str):
                lines.append(self.wrap_text(f"Likelihood: {clean_citations(likelihood)}", indent=3))
                lines.append("")

            # Indicators to watch
            indicators = prediction.get("indicators_to_watch", [])
            if indicators and isinstance(indicators, list):
                lines.append("   Indicators to watch:")
                for indicator in indicators:
                    if isinstance(indicator, str):
                        lines.append(
                            self.wrap_text(
                                f"* {clean_citations(indicator)}", indent=5, subsequent_indent=7
                            )
                        )
                lines.append("")

        return lines

    def format_compact_summary(self, report_data: dict[str, Any]) -> str:
        """
        Format compact one-line summary of report

        Args:
            report_data: Report data from NewsletterSystem

        Returns:
            One-line summary string
        """
        duration = report_data.get("duration_hours", 0)
        articles = report_data.get("articles_analyzed", 0)
        report_type = report_data.get("report_type", "custom")

        return f"{report_type.upper()} BRIEF: {articles} articles analyzed over {duration:.1f}h"
