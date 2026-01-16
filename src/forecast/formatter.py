"""
Forecast Formatter
Formats certainty-based forecasts for terminal display and HTML/JSON reports
"""

import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config.settings import settings


class ForecastFormatter:
    """Formats certainty-based forecast data for human-readable output"""

    def _normalize_item(self, item: Any) -> dict:
        """Normalize a forecast item to a dict, handling strings"""
        if isinstance(item, str):
            return {"forecast": item, "timeline": "Unknown"}
        if isinstance(item, dict):
            return item
        return {"forecast": str(item), "timeline": "Unknown"}

    def format_forecast(self, forecast: dict[str, Any], max_width: int = 80) -> str:
        """
        Format forecast for terminal display

        Args:
            forecast: Forecast dictionary from orchestrator
            max_width: Maximum line width for wrapping

        Returns:
            Formatted string for terminal output
        """
        lines = []
        forecast_data = forecast.get("forecast_data", forecast)

        # Header
        lines.append("\n" + "=" * max_width)
        lines.append("CERTAINTY-BASED FORECAST")
        generated_at = forecast.get("generated_at", datetime.now().isoformat())
        lines.append(f"Generated: {generated_at[:10]}")
        lines.append("=" * max_width)
        lines.append("")

        # Section 1: Known Knowns
        self._format_known_knowns(lines, forecast_data, max_width)

        # Section 2: Known Unknowns
        self._format_known_unknowns(lines, forecast_data, max_width)

        # Section 3: Unknown Unknowns
        self._format_unknown_unknowns(lines, forecast_data, max_width)

        # Footer
        lines.append("")
        lines.append("=" * max_width)

        # Data sources
        data_sources = forecast_data.get("data_sources_summary", "")
        if data_sources:
            lines.append("")
            wrapped = textwrap.fill(
                f"Data Sources: {data_sources}", width=max_width, subsequent_indent="  "
            )
            lines.append(wrapped)

        lines.append("")

        return "\n".join(lines)

    def _format_known_knowns(
        self, lines: list[str], forecast_data: dict[str, Any], max_width: int
    ) -> None:
        """Format Known Knowns section (certain/near-certain forecasts)"""
        lines.append("-" * max_width)
        lines.append("KNOWN KNOWNS (Certain or Near-Certain)")
        lines.append("-" * max_width)
        lines.append("")

        known_knowns = forecast_data.get("known_knowns", [])
        if not known_knowns:
            lines.append("  No certain forecasts identified.")
            lines.append("")
            return

        for i, raw_item in enumerate(known_knowns, 1):
            item = self._normalize_item(raw_item)
            forecast_text = item.get("forecast", "N/A")
            timeline = item.get("timeline", "Unknown")
            basis = item.get("basis", "")
            impact = item.get("impact", "")

            lines.append(f"{i}. {forecast_text}")
            lines.append(f"   Timeline: {timeline}")

            if basis:
                wrapped = textwrap.fill(
                    f"   Basis: {basis}", width=max_width, subsequent_indent="          "
                )
                lines.append(wrapped)

            if impact:
                wrapped = textwrap.fill(
                    f"   Impact: {impact}", width=max_width, subsequent_indent="          "
                )
                lines.append(wrapped)

            lines.append("")

    def _format_known_unknowns(
        self, lines: list[str], forecast_data: dict[str, Any], max_width: int
    ) -> None:
        """Format Known Unknowns section (evidence-based projections)"""
        lines.append("-" * max_width)
        lines.append("KNOWN UNKNOWNS (Evidence-Based Projections)")
        lines.append("-" * max_width)
        lines.append("")

        known_unknowns = forecast_data.get("known_unknowns", [])
        if not known_unknowns:
            lines.append("  No evidence-based projections identified.")
            lines.append("")
            return

        for i, raw_item in enumerate(known_unknowns, 1):
            item = self._normalize_item(raw_item)
            forecast_text = item.get("forecast", "N/A")
            timeline = item.get("timeline", "Unknown")
            evidence = item.get("evidence", "")
            possible_outcomes = item.get("possible_outcomes", [])
            key_factors = item.get("key_factors", [])

            lines.append(f"{i}. {forecast_text}")
            lines.append(f"   Timeline: {timeline}")

            if evidence:
                wrapped = textwrap.fill(
                    f"   Evidence: {evidence}", width=max_width, subsequent_indent="             "
                )
                lines.append(wrapped)

            if possible_outcomes:
                lines.append("   Possible Outcomes:")
                for outcome in possible_outcomes[:3]:
                    wrapped = textwrap.fill(
                        f"     - {outcome}", width=max_width, subsequent_indent="       "
                    )
                    lines.append(wrapped)

            if key_factors:
                lines.append("   Key Factors:")
                for factor in key_factors[:3]:
                    wrapped = textwrap.fill(
                        f"     - {factor}", width=max_width, subsequent_indent="       "
                    )
                    lines.append(wrapped)

            lines.append("")

    def _format_unknown_unknowns(
        self, lines: list[str], forecast_data: dict[str, Any], max_width: int
    ) -> None:
        """Format Unknown Unknowns section (weak signal projections)"""
        lines.append("-" * max_width)
        lines.append("UNKNOWN UNKNOWNS (Weak Signal Projections)")
        lines.append("-" * max_width)
        lines.append("")

        unknown_unknowns = forecast_data.get("unknown_unknowns", [])
        if not unknown_unknowns:
            lines.append("  No weak signal projections identified.")
            lines.append("")
            return

        for i, raw_item in enumerate(unknown_unknowns, 1):
            item = self._normalize_item(raw_item)
            forecast_text = item.get("forecast", "N/A")
            timeline = item.get("timeline", "Unknown")
            weak_signal = item.get("weak_signal", "")
            potential_impact = item.get("potential_impact", "")
            why_plausible = item.get("why_plausible", "")

            lines.append(f"{i}. {forecast_text}")
            lines.append(f"   Timeline: {timeline}")

            if weak_signal:
                wrapped = textwrap.fill(
                    f"   Weak Signal: {weak_signal}",
                    width=max_width,
                    subsequent_indent="                ",
                )
                lines.append(wrapped)

            if potential_impact:
                wrapped = textwrap.fill(
                    f"   If Occurs: {potential_impact}",
                    width=max_width,
                    subsequent_indent="              ",
                )
                lines.append(wrapped)

            if why_plausible:
                wrapped = textwrap.fill(
                    f"   Why Plausible: {why_plausible}",
                    width=max_width,
                    subsequent_indent="                  ",
                )
                lines.append(wrapped)

            lines.append("")

    def save_html_report(self, result: dict[str, Any]) -> Path:
        """
        Generate and save HTML report

        Args:
            result: Forecast result dictionary from orchestrator

        Returns:
            Path to saved HTML file
        """
        forecast = result.get("forecast", {})
        # Handle case where forecast might be a string instead of dict
        if isinstance(forecast, str):
            forecast = {"forecast_data": {}, "generated_at": datetime.now().isoformat()}
        forecast_data = forecast.get("forecast_data", {})
        # Handle case where forecast_data might be a string
        if isinstance(forecast_data, str):
            forecast_data = {}

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<title>InsightWeaver Forecast Report</title>",
            "<style>",
            "body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }",
            ".container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-top: 0; }",
            "h2 { color: #34495e; margin-top: 30px; border-bottom: 2px solid #bdc3c7; padding-bottom: 8px; }",
            ".metadata { background: #ecf0f1; padding: 15px; border-radius: 5px; margin-bottom: 25px; }",
            ".forecast-item { background: #fafafa; padding: 18px; margin: 12px 0; border-radius: 6px; border-left: 4px solid #3498db; }",
            ".known-knowns .forecast-item { border-left-color: #27ae60; }",
            ".known-unknowns .forecast-item { border-left-color: #f39c12; }",
            ".unknown-unknowns .forecast-item { border-left-color: #9b59b6; }",
            ".forecast-text { font-size: 16px; font-weight: 600; color: #2c3e50; margin-bottom: 8px; }",
            ".timeline { display: inline-block; background: #3498db; color: white; padding: 3px 10px; border-radius: 12px; font-size: 13px; margin-bottom: 10px; }",
            ".known-knowns .timeline { background: #27ae60; }",
            ".known-unknowns .timeline { background: #f39c12; }",
            ".unknown-unknowns .timeline { background: #9b59b6; }",
            ".detail { color: #555; font-size: 14px; margin: 6px 0; line-height: 1.5; }",
            ".detail strong { color: #34495e; }",
            ".outcomes-list { margin: 8px 0 8px 20px; padding: 0; }",
            ".outcomes-list li { margin: 4px 0; color: #555; }",
            ".section-intro { color: #7f8c8d; font-style: italic; margin-bottom: 15px; }",
            ".footer { text-align: center; color: #95a5a6; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ecf0f1; }",
            "</style>",
            "</head>",
            "<body>",
            "<div class='container'>",
            "<h1>InsightWeaver Forecast Report</h1>",
        ]

        # Metadata
        generated_at = forecast.get("generated_at", datetime.now().isoformat())
        articles = forecast.get("articles_analyzed", 0)
        html_parts.append("<div class='metadata'>")
        html_parts.append(f"<strong>Generated:</strong> {generated_at[:19].replace('T', ' ')}<br>")
        html_parts.append(f"<strong>Articles Analyzed:</strong> {articles}")
        html_parts.append("</div>")

        # Known Knowns
        html_parts.append("<div class='known-knowns'>")
        html_parts.append("<h2>Known Knowns</h2>")
        html_parts.append(
            "<p class='section-intro'>Certain or near-certain forecasts based on scheduled events, announced plans, or legal requirements.</p>"
        )

        known_knowns = forecast_data.get("known_knowns", [])
        if known_knowns:
            for raw_item in known_knowns:
                item = self._normalize_item(raw_item)
                html_parts.append("<div class='forecast-item'>")
                html_parts.append(f"<div class='forecast-text'>{item.get('forecast', 'N/A')}</div>")
                html_parts.append(
                    f"<span class='timeline'>{item.get('timeline', 'Unknown')}</span>"
                )
                if item.get("basis"):
                    html_parts.append(
                        f"<div class='detail'><strong>Basis:</strong> {item['basis']}</div>"
                    )
                if item.get("impact"):
                    html_parts.append(
                        f"<div class='detail'><strong>Impact:</strong> {item['impact']}</div>"
                    )
                html_parts.append("</div>")
        else:
            html_parts.append("<p>No certain forecasts identified.</p>")
        html_parts.append("</div>")

        # Known Unknowns
        html_parts.append("<div class='known-unknowns'>")
        html_parts.append("<h2>Known Unknowns</h2>")
        html_parts.append(
            "<p class='section-intro'>Evidence-based projections with significant supporting data but uncertain outcomes.</p>"
        )

        known_unknowns = forecast_data.get("known_unknowns", [])
        if known_unknowns:
            for raw_item in known_unknowns:
                item = self._normalize_item(raw_item)
                html_parts.append("<div class='forecast-item'>")
                html_parts.append(f"<div class='forecast-text'>{item.get('forecast', 'N/A')}</div>")
                html_parts.append(
                    f"<span class='timeline'>{item.get('timeline', 'Unknown')}</span>"
                )
                if item.get("evidence"):
                    html_parts.append(
                        f"<div class='detail'><strong>Evidence:</strong> {item['evidence']}</div>"
                    )
                outcomes = item.get("possible_outcomes", [])
                if outcomes:
                    html_parts.append(
                        "<div class='detail'><strong>Possible Outcomes:</strong></div>"
                    )
                    html_parts.append("<ul class='outcomes-list'>")
                    for outcome in outcomes[:4]:
                        html_parts.append(f"<li>{outcome}</li>")
                    html_parts.append("</ul>")
                factors = item.get("key_factors", [])
                if factors:
                    html_parts.append(
                        f"<div class='detail'><strong>Key Factors:</strong> {', '.join(factors[:4])}</div>"
                    )
                html_parts.append("</div>")
        else:
            html_parts.append("<p>No evidence-based projections identified.</p>")
        html_parts.append("</div>")

        # Unknown Unknowns
        html_parts.append("<div class='unknown-unknowns'>")
        html_parts.append("<h2>Unknown Unknowns</h2>")
        html_parts.append(
            "<p class='section-intro'>Speculative forecasts based on weak signals and emerging patterns.</p>"
        )

        unknown_unknowns = forecast_data.get("unknown_unknowns", [])
        if unknown_unknowns:
            for raw_item in unknown_unknowns:
                item = self._normalize_item(raw_item)
                html_parts.append("<div class='forecast-item'>")
                html_parts.append(f"<div class='forecast-text'>{item.get('forecast', 'N/A')}</div>")
                html_parts.append(
                    f"<span class='timeline'>{item.get('timeline', 'Unknown')}</span>"
                )
                if item.get("weak_signal"):
                    html_parts.append(
                        f"<div class='detail'><strong>Weak Signal:</strong> {item['weak_signal']}</div>"
                    )
                if item.get("potential_impact"):
                    html_parts.append(
                        f"<div class='detail'><strong>If Occurs:</strong> {item['potential_impact']}</div>"
                    )
                if item.get("why_plausible"):
                    html_parts.append(
                        f"<div class='detail'><strong>Why Plausible:</strong> {item['why_plausible']}</div>"
                    )
                html_parts.append("</div>")
        else:
            html_parts.append("<p>No weak signal projections identified.</p>")
        html_parts.append("</div>")

        # Data sources
        data_sources = forecast_data.get("data_sources_summary", "")
        if data_sources:
            html_parts.append(
                f"<div class='detail' style='margin-top: 20px;'><strong>Data Sources:</strong> {data_sources}</div>"
            )

        # Footer
        html_parts.append(
            f"<div class='footer'>Generated by InsightWeaver on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>"
        )
        html_parts.append("</div>")
        html_parts.append("</body></html>")

        # Save to file
        output_dir = settings.forecasts_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"forecast_{result['run_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = output_dir / filename

        filepath.write_text("\n".join(html_parts))

        return filepath

    def save_json_report(self, result: dict[str, Any]) -> Path:
        """
        Generate and save JSON report for programmatic access

        Args:
            result: Forecast result dictionary from orchestrator

        Returns:
            Path to saved JSON file
        """
        output_dir = settings.forecasts_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"forecast_{result['run_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_dir / filename

        forecast = result.get("forecast", {})
        # Handle case where forecast might be a string instead of dict
        if isinstance(forecast, str):
            forecast = {"forecast_data": {}, "generated_at": datetime.now().isoformat()}
        forecast_data = forecast.get("forecast_data", {})
        # Handle case where forecast_data might be a string
        if isinstance(forecast_data, str):
            forecast_data = {}

        json_output = {
            "version": "2.0",
            "type": "certainty_based_forecast",
            "generated_at": datetime.now().isoformat(),
            "run_id": result["run_id"],
            "articles_analyzed": forecast.get("articles_analyzed", 0),
            "known_knowns": forecast_data.get("known_knowns", []),
            "known_unknowns": forecast_data.get("known_unknowns", []),
            "unknown_unknowns": forecast_data.get("unknown_unknowns", []),
            "data_sources_summary": forecast_data.get("data_sources_summary", ""),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)

        return filepath
