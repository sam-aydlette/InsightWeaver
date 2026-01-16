"""
Executive Forecast Formatter
Condensed multi-horizon forecast output for quick consumption
"""

import textwrap
from collections import Counter
from datetime import datetime
from typing import Any


class ExecutiveForecastFormatter:
    """
    Formats multi-horizon forecasts as executive briefing (1-2 slides)

    Condensed output focuses on:
    - Top 2-3 trends with projected outcomes across horizons
    - Action triggers (early warning signals) by horizon
    - Critical uncertainties
    """

    def __init__(self, max_width: int = 80):
        """
        Initialize executive formatter

        Args:
            max_width: Maximum line width for terminal output
        """
        self.max_width = max_width

    def format_executive_briefing(
        self, forecasts: list[dict[str, Any]], report_path: str = None
    ) -> str:
        """
        Create consolidated executive briefing across all horizons

        Args:
            forecasts: List of forecast dicts (from orchestrator result)
            report_path: Optional path to HTML report

        Returns:
            Formatted briefing string (30-50 lines)
        """
        if not forecasts:
            return "No forecasts available"

        # Normalize forecast structure - extract forecast_data if nested
        normalized_forecasts = []
        for f in forecasts:
            if "forecast_data" in f:
                # Merge metadata with forecast_data
                forecast = f["forecast_data"].copy()
                forecast["time_horizon"] = f.get("time_horizon")
                forecast["horizon_months"] = f.get("horizon_months")
                normalized_forecasts.append(forecast)
            else:
                # Already in expected format
                normalized_forecasts.append(f)

        # Sort forecasts by horizon
        sorted_forecasts = sorted(normalized_forecasts, key=lambda f: f.get("horizon_months", 0))
        horizons = [f["time_horizon"] for f in sorted_forecasts]

        # Extract top trends
        top_trends = self._extract_top_trends(sorted_forecasts)

        # Build output sections
        lines = []
        lines.append("=" * self.max_width)
        lines.append("FORECAST EXECUTIVE BRIEFING")

        # Header with metadata
        generated = datetime.now().strftime("%Y-%m-%d %H:%M")
        horizon_str = ", ".join(horizons)
        lines.append(f"Generated: {generated} | Horizons: {horizon_str}")
        lines.append("=" * self.max_width)
        lines.append("")

        # Top Trends section
        if top_trends:
            lines.append("TOP TRENDS (Projected Outcomes)")
            lines.append("")

            # Build trend comparison table
            table_lines = self._build_trend_comparison_table(top_trends, sorted_forecasts)
            lines.extend(table_lines)
            lines.append("")

        # Action Triggers section
        lines.append("WATCH FOR (Action Triggers - Early Warning Signals)")
        lines.append("")

        for forecast in sorted_forecasts:
            horizon = forecast["time_horizon"]
            triggers = self._extract_action_triggers(forecast)

            if triggers:
                lines.append(f"{horizon.upper()} Horizon:")
                for trigger in triggers[:3]:  # Limit to top 3 per horizon
                    wrapped = textwrap.fill(
                        f"  • {trigger}", width=self.max_width, subsequent_indent="    "
                    )
                    lines.append(wrapped)
                lines.append("")

        # Key Uncertainties section
        lines.append("=" * self.max_width)
        lines.append("KEY UNCERTAINTIES")

        critical_uncertainties = self._identify_critical_uncertainties(sorted_forecasts)
        for uncertainty in critical_uncertainties[:2]:  # Top 2 most critical
            wrapped = textwrap.fill(
                f"• {uncertainty}", width=self.max_width, subsequent_indent="  "
            )
            lines.append(wrapped)

        lines.append("")
        lines.append("For detailed analysis, run: insightweaver forecast --full")
        if report_path:
            lines.append(f"HTML report: {report_path}")
        lines.append("=" * self.max_width)

        return "\n".join(lines)

    def _extract_top_trends(self, forecasts: list[dict[str, Any]]) -> list[str]:
        """
        Extract top 2-3 trends appearing most frequently across horizons

        Args:
            forecasts: List of forecast dictionaries

        Returns:
            List of trend names (top 2-3)
        """
        # Count trend occurrences across all horizons
        trend_counter = Counter()

        for forecast in forecasts:
            trends = forecast.get("trend_extrapolations", [])
            for trend in trends:
                trend_name = trend.get("trend", "")
                if trend_name:
                    # Normalize trend name for counting
                    normalized_name = self._normalize_trend_name(trend_name)
                    trend_counter[normalized_name] += 1

        # Get top 3 most common trends
        top_trends = [name for name, count in trend_counter.most_common(3)]

        return top_trends

    def _normalize_trend_name(self, trend_name: str) -> str:
        """
        Normalize trend name for comparison across horizons

        Args:
            trend_name: Raw trend description

        Returns:
            Normalized trend name (shortened, key phrases extracted)
        """
        # Simple normalization: take first 50 chars, strip whitespace
        # In production, could use more sophisticated phrase extraction
        normalized = trend_name.strip()[:50]

        # Extract key phrases if trend is long
        if len(trend_name) > 50:
            # Try to break at sentence boundary
            sentences = trend_name.split(".")
            if sentences:
                normalized = sentences[0].strip()

        return normalized

    def _build_trend_comparison_table(
        self, top_trends: list[str], forecasts: list[dict[str, Any]]
    ) -> list[str]:
        """
        Build ASCII table showing trend evolution across horizons

        Args:
            top_trends: List of top trend names
            forecasts: Sorted list of forecasts

        Returns:
            List of formatted table lines
        """
        lines = []

        # Table header
        horizons = [f["time_horizon"] for f in forecasts]
        col_width = 16  # Width for each horizon column
        trend_col_width = 24  # Width for trend name column

        header = f"{'Trend':<{trend_col_width}}"
        for horizon in horizons:
            header += f"{horizon:^{col_width}}"
        lines.append(header)
        lines.append("-" * self.max_width)

        # Build rows for each trend
        for trend_name in top_trends:
            # Find this trend in each forecast
            row_data = self._get_trend_outcomes_by_horizon(trend_name, forecasts)

            # Truncate trend name if too long
            display_name = (
                trend_name[: trend_col_width - 1]
                if len(trend_name) > trend_col_width
                else trend_name
            )
            row = f"{display_name:<{trend_col_width}}"

            for horizon in horizons:
                outcome = row_data.get(horizon, "-")
                # Truncate outcome to fit column
                outcome_display = outcome[: col_width - 1] if len(outcome) > col_width else outcome
                row += f"{outcome_display:<{col_width}}"

            lines.append(row)

            # Add blank line between trends for readability
            if trend_name != top_trends[-1]:
                lines.append("")

        lines.append("-" * self.max_width)

        return lines

    def _get_trend_outcomes_by_horizon(
        self, trend_name: str, forecasts: list[dict[str, Any]]
    ) -> dict[str, str]:
        """
        Get projected outcomes for a specific trend across all horizons

        Args:
            trend_name: Trend to find
            forecasts: List of forecast dictionaries

        Returns:
            Dict mapping horizon -> projected outcome
        """
        outcomes = {}

        for forecast in forecasts:
            horizon = forecast["time_horizon"]
            trends = forecast.get("trend_extrapolations", [])

            # Find matching trend
            for trend in trends:
                if self._trends_match(trend_name, trend.get("trend", "")):
                    # Extract concise outcome
                    outcome = trend.get("projected_outcome", "")
                    if outcome:
                        # Shorten to key phrase (first sentence)
                        outcome = self._extract_key_phrase(outcome)
                        outcomes[horizon] = outcome
                        break

        return outcomes

    def _trends_match(self, trend1: str, trend2: str) -> bool:
        """
        Check if two trend descriptions refer to the same trend

        Args:
            trend1: First trend description
            trend2: Second trend description

        Returns:
            True if trends match
        """
        # Simple matching: normalize both and check if one contains the other
        norm1 = self._normalize_trend_name(trend1).lower()
        norm2 = self._normalize_trend_name(trend2).lower()

        return norm1 in norm2 or norm2 in norm1

    def _extract_key_phrase(self, text: str, max_length: int = 15) -> str:
        """
        Extract key phrase from longer text

        Args:
            text: Full text
            max_length: Maximum phrase length

        Returns:
            Shortened key phrase
        """
        # Take first sentence
        sentences = text.split(".")
        phrase = sentences[0].strip()

        # If still too long, take first N words
        if len(phrase) > max_length:
            words = phrase.split()
            phrase = " ".join(words[:3])

        return phrase[:max_length]

    def _extract_action_triggers(self, forecast: dict[str, Any]) -> list[str]:
        """
        Extract action triggers (early warning signals) from forecast

        Pulls from:
        - Scenario trigger_events
        - Known unknowns

        Args:
            forecast: Forecast dictionary

        Returns:
            List of trigger/signal strings
        """
        triggers = []

        # Get triggers from scenarios
        scenarios = forecast.get("scenarios", [])
        for scenario in scenarios:
            scenario_triggers = scenario.get("trigger_events", [])
            triggers.extend(scenario_triggers)

        # Get triggers from known unknowns
        event_risks = forecast.get("event_risks", {})
        known_unknowns = event_risks.get("known_unknowns", [])
        for unknown in known_unknowns:
            uncertainty = unknown.get("uncertainty", "")
            if uncertainty:
                triggers.append(uncertainty)

        # Deduplicate and return
        unique_triggers = list(dict.fromkeys(triggers))  # Preserves order

        return unique_triggers

    def _identify_critical_uncertainties(self, forecasts: list[dict[str, Any]]) -> list[str]:
        """
        Identify most critical uncertainties across all forecasts

        Args:
            forecasts: List of forecast dictionaries

        Returns:
            List of critical uncertainty strings (top 2-3)
        """
        # Collect all uncertainties
        all_uncertainties = []

        for forecast in forecasts:
            # Get forecast-level uncertainties
            key_uncertainties = forecast.get("key_uncertainties", [])
            all_uncertainties.extend(key_uncertainties)

            # Get trend-level uncertainties
            trends = forecast.get("trend_extrapolations", [])
            for trend in trends:
                trend_uncertainties = trend.get("uncertainties", [])
                all_uncertainties.extend(trend_uncertainties)

        # Count occurrences to find most common/critical
        uncertainty_counter = Counter(all_uncertainties)

        # Return top 2-3 most mentioned uncertainties
        top_uncertainties = [unc for unc, count in uncertainty_counter.most_common(3)]

        return top_uncertainties
