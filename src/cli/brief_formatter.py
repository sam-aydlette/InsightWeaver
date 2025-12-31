"""
Brief Report Terminal Formatter
Format intelligence reports for terminal display
"""
from typing import Dict, Any
import textwrap


class BriefFormatter:
    """Format intelligence brief reports for terminal display"""

    @staticmethod
    def format_report(report_data: Dict[str, Any], max_width: int = 80) -> str:
        """
        Format complete intelligence report for terminal

        Args:
            report_data: Report data from NewsletterSystem
            max_width: Maximum line width for text wrapping

        Returns:
            Formatted report string
        """
        lines = []

        # Header
        lines.append("\n" + "=" * max_width)
        lines.append("INTELLIGENCE BRIEF")
        lines.append("=" * max_width)

        # Time window
        start = report_data.get('start_date')
        end = report_data.get('end_date')
        duration = report_data.get('duration_hours', 0)

        if start and end:
            lines.append(f"\nTime Window: {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')} ({duration:.1f}h)")

        lines.append(f"Articles Analyzed: {report_data.get('articles_analyzed', 0)}")
        lines.append(f"Report Type: {report_data.get('report_type', 'custom').upper()}")
        lines.append("")

        # Executive Summary
        exec_summary = report_data.get('executive_summary', '')
        if exec_summary and isinstance(exec_summary, str) and exec_summary != "No articles found in the specified time window.":
            lines.append("-" * max_width)
            lines.append("EXECUTIVE SUMMARY")
            lines.append("-" * max_width)
            lines.append("")
            wrapped = textwrap.fill(exec_summary, width=max_width)
            lines.append(wrapped)
            lines.append("")

        # Synthesis Data
        synthesis_data = report_data.get('synthesis_data', {})

        if synthesis_data:
            # Bottom Line
            bottom_line = synthesis_data.get('bottom_line', '')
            if bottom_line and isinstance(bottom_line, str):
                lines.append("-" * max_width)
                lines.append("BOTTOM LINE")
                lines.append("-" * max_width)
                lines.append("")
                wrapped = textwrap.fill(bottom_line, width=max_width)
                lines.append(wrapped)
                lines.append("")

            # Trends and Patterns
            trends = synthesis_data.get('trends_and_patterns', [])
            if trends and isinstance(trends, list):
                lines.append("-" * max_width)
                lines.append("KEY TRENDS & PATTERNS")
                lines.append("-" * max_width)
                lines.append("")

                for i, trend in enumerate(trends, 1):
                    if not isinstance(trend, dict):
                        continue

                    # Trend header
                    trend_title = trend.get('trend', 'Unknown Trend')
                    if isinstance(trend_title, str):
                        lines.append(f"{i}. {trend_title}")
                        lines.append("")

                    # Description
                    description = trend.get('description', '')
                    if description and isinstance(description, str):
                        wrapped = textwrap.fill(description, width=max_width - 3, initial_indent='   ', subsequent_indent='   ')
                        lines.append(wrapped)
                        lines.append("")

                    # Evidence
                    evidence = trend.get('evidence', [])
                    if evidence and isinstance(evidence, list):
                        lines.append("   Evidence:")
                        for item in evidence:
                            if isinstance(item, str):
                                wrapped = textwrap.fill(f"• {item}", width=max_width - 5, initial_indent='     ', subsequent_indent='       ')
                                lines.append(wrapped)
                        lines.append("")

                    # Significance
                    significance = trend.get('significance', '')
                    if significance and isinstance(significance, str):
                        wrapped = textwrap.fill(f"Significance: {significance}", width=max_width - 3, initial_indent='   ', subsequent_indent='   ')
                        lines.append(wrapped)
                        lines.append("")

            # Priority Events
            events = synthesis_data.get('priority_events', [])
            if events and isinstance(events, list):
                lines.append("-" * max_width)
                lines.append("PRIORITY EVENTS")
                lines.append("-" * max_width)
                lines.append("")

                for i, event in enumerate(events, 1):
                    if not isinstance(event, dict):
                        continue

                    # Event header
                    event_title = event.get('event', 'Unknown Event')
                    priority = event.get('priority', 'MEDIUM')
                    if isinstance(event_title, str) and isinstance(priority, str):
                        lines.append(f"{i}. [{priority}] {event_title}")
                        lines.append("")

                    # Summary
                    summary = event.get('summary', '')
                    if summary and isinstance(summary, str):
                        wrapped = textwrap.fill(summary, width=max_width - 3, initial_indent='   ', subsequent_indent='   ')
                        lines.append(wrapped)
                        lines.append("")

                    # Why it matters
                    why_matters = event.get('why_it_matters', '')
                    if why_matters and isinstance(why_matters, str):
                        wrapped = textwrap.fill(f"Why it matters: {why_matters}", width=max_width - 3, initial_indent='   ', subsequent_indent='   ')
                        lines.append(wrapped)
                        lines.append("")

                    # Context
                    context = event.get('context', '')
                    if context and isinstance(context, str):
                        wrapped = textwrap.fill(f"Context: {context}", width=max_width - 3, initial_indent='   ', subsequent_indent='   ')
                        lines.append(wrapped)
                        lines.append("")

            # Predictions and Scenarios
            predictions = synthesis_data.get('predictions_scenarios', [])
            if predictions and isinstance(predictions, list):
                lines.append("-" * max_width)
                lines.append("PREDICTIONS & SCENARIOS")
                lines.append("-" * max_width)
                lines.append("")

                for i, prediction in enumerate(predictions, 1):
                    if not isinstance(prediction, dict):
                        continue

                    # Prediction header
                    pred_title = prediction.get('scenario', 'Unknown Scenario')
                    timeframe = prediction.get('timeframe', 'Unknown')
                    if isinstance(pred_title, str) and isinstance(timeframe, str):
                        lines.append(f"{i}. {pred_title} ({timeframe})")
                        lines.append("")

                    # Prediction text
                    pred_text = prediction.get('prediction', '')
                    if pred_text and isinstance(pred_text, str):
                        wrapped = textwrap.fill(pred_text, width=max_width - 3, initial_indent='   ', subsequent_indent='   ')
                        lines.append(wrapped)
                        lines.append("")

                    # Likelihood
                    likelihood = prediction.get('likelihood', '')
                    if likelihood and isinstance(likelihood, str):
                        wrapped = textwrap.fill(f"Likelihood: {likelihood}", width=max_width - 3, initial_indent='   ', subsequent_indent='   ')
                        lines.append(wrapped)
                        lines.append("")

                    # Indicators to watch
                    indicators = prediction.get('indicators_to_watch', [])
                    if indicators and isinstance(indicators, list):
                        lines.append("   Indicators to watch:")
                        for indicator in indicators:
                            if isinstance(indicator, str):
                                wrapped = textwrap.fill(f"• {indicator}", width=max_width - 5, initial_indent='     ', subsequent_indent='       ')
                                lines.append(wrapped)
                        lines.append("")

        # Footer
        lines.append("=" * max_width)
        lines.append("End of Intelligence Brief")
        lines.append("=" * max_width)
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_compact_summary(report_data: Dict[str, Any]) -> str:
        """
        Format compact one-line summary of report

        Args:
            report_data: Report data from NewsletterSystem

        Returns:
            One-line summary string
        """
        duration = report_data.get('duration_hours', 0)
        articles = report_data.get('articles_analyzed', 0)
        report_type = report_data.get('report_type', 'custom')

        return f"{report_type.upper()} BRIEF: {articles} articles analyzed over {duration:.1f}h"
