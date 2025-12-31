"""
Forecast Formatter
Formats forecast data for terminal display and HTML reports
"""

import textwrap
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


class ForecastFormatter:
    """Formats forecast data for human-readable output"""

    def format_forecast(self, forecast: Dict[str, Any], max_width: int = 80) -> str:
        """
        Format forecast for terminal display

        Args:
            forecast: Forecast dictionary from database
            max_width: Maximum line width for wrapping

        Returns:
            Formatted string for terminal output
        """
        lines = []

        # Header
        lines.append("\n" + "=" * max_width)
        lines.append(f"{forecast['time_horizon'].upper()} FORECAST")
        lines.append(f"Target Date: {forecast['target_date']}")
        lines.append("=" * max_width)
        lines.append("")

        forecast_data = forecast['forecast_data']

        # Section 1: Trend Extrapolations
        self._format_trend_extrapolations(lines, forecast_data, max_width)

        # Section 2: Scenarios
        self._format_scenarios(lines, forecast_data, max_width)

        # Section 3: Historical Patterns
        self._format_historical_patterns(lines, forecast_data, max_width)

        # Section 4: Causal Chains
        self._format_causal_chains(lines, forecast_data, max_width)

        # Section 5: Event Risks
        self._format_event_risks(lines, forecast_data, max_width)

        # Footer
        lines.append("")
        lines.append("=" * max_width)

        # Key Uncertainties
        if forecast_data.get('key_uncertainties'):
            lines.append("")
            lines.append("KEY UNCERTAINTIES:")
            for uncertainty in forecast_data['key_uncertainties']:
                wrapped = textwrap.fill(f"  - {uncertainty}", width=max_width, subsequent_indent="    ")
                lines.append(wrapped)

        lines.append("")

        return "\n".join(lines)

    def _format_trend_extrapolations(
        self,
        lines: List[str],
        forecast_data: Dict[str, Any],
        max_width: int
    ) -> None:
        """Format trend extrapolation section"""
        lines.append("-" * max_width)
        lines.append("1. TREND EXTRAPOLATIONS")
        lines.append("-" * max_width)
        lines.append("")

        trends = forecast_data.get('trend_extrapolations', [])
        for i, trend in enumerate(trends, 1):
            lines.append(f"Trend {i}: {trend.get('trend', 'N/A')}")

            current = trend.get('current_state', '')
            if current:
                wrapped = textwrap.fill(f"  Current: {current}", width=max_width, subsequent_indent="           ")
                lines.append(wrapped)

            trajectory = trend.get('projected_trajectory', '')
            if trajectory:
                wrapped = textwrap.fill(f"  Trajectory: {trajectory}", width=max_width, subsequent_indent="              ")
                lines.append(wrapped)

            outcome = trend.get('projected_outcome', '')
            if outcome:
                wrapped = textwrap.fill(f"  Outcome: {outcome}", width=max_width, subsequent_indent="           ")
                lines.append(wrapped)

            uncertainties = trend.get('uncertainties', [])
            if uncertainties:
                lines.append("  Uncertainties:")
                for unc in uncertainties:
                    wrapped = textwrap.fill(f"    - {unc}", width=max_width, subsequent_indent="      ")
                    lines.append(wrapped)

            lines.append("")

        lines.append("")

    def _format_scenarios(
        self,
        lines: List[str],
        forecast_data: Dict[str, Any],
        max_width: int
    ) -> None:
        """Format scenario modeling section"""
        lines.append("-" * max_width)
        lines.append("2. SCENARIO MODELING")
        lines.append("-" * max_width)
        lines.append("")

        scenarios = forecast_data.get('scenarios', [])
        for scenario in scenarios:
            scenario_type = scenario.get('type', 'unknown').upper()
            name = scenario.get('name', 'Unnamed Scenario')

            lines.append(f"[{scenario_type}] {name}")

            plausibility = scenario.get('plausibility', '')
            if plausibility:
                wrapped = textwrap.fill(f"  Plausibility: {plausibility}", width=max_width, subsequent_indent="                ")
                lines.append(wrapped)

            predictions = scenario.get('predictions', [])
            if predictions:
                lines.append("  Predictions:")
                for pred in predictions[:5]:  # Limit to top 5
                    wrapped = textwrap.fill(f"    - {pred}", width=max_width, subsequent_indent="      ")
                    lines.append(wrapped)

            assumptions = scenario.get('key_assumptions', [])
            if assumptions:
                lines.append("  Key Assumptions:")
                for assumption in assumptions[:3]:  # Limit to top 3
                    wrapped = textwrap.fill(f"    - {assumption}", width=max_width, subsequent_indent="      ")
                    lines.append(wrapped)

            lines.append("")

        lines.append("")

    def _format_historical_patterns(
        self,
        lines: List[str],
        forecast_data: Dict[str, Any],
        max_width: int
    ) -> None:
        """Format pattern recognition section"""
        lines.append("-" * max_width)
        lines.append("3. HISTORICAL PATTERNS")
        lines.append("-" * max_width)
        lines.append("")

        patterns = forecast_data.get('historical_patterns', [])
        for i, pattern in enumerate(patterns, 1):
            pattern_type = pattern.get('pattern_type', 'unknown').capitalize()
            pattern_desc = pattern.get('pattern', 'N/A')

            lines.append(f"Pattern {i}: {pattern_type}")
            wrapped = textwrap.fill(f"  {pattern_desc}", width=max_width, subsequent_indent="  ")
            lines.append(wrapped)

            historical_period = pattern.get('historical_period', '')
            if historical_period:
                lines.append(f"  Historical Period: {historical_period}")

            implications = pattern.get('implications', '')
            if implications:
                wrapped = textwrap.fill(f"  Implications: {implications}", width=max_width, subsequent_indent="                ")
                lines.append(wrapped)

            lines.append("")

        lines.append("")

    def _format_causal_chains(
        self,
        lines: List[str],
        forecast_data: Dict[str, Any],
        max_width: int
    ) -> None:
        """Format causal chain analysis section"""
        lines.append("-" * max_width)
        lines.append("4. CAUSAL CHAIN ANALYSIS")
        lines.append("-" * max_width)
        lines.append("")

        chains = forecast_data.get('causal_chains', [])
        for i, chain in enumerate(chains, 1):
            name = chain.get('chain_name', f'Chain {i}')
            time_months = chain.get('time_to_unfold_months', 0)

            lines.append(f"{name} ({time_months}mo to unfold)")

            initial = chain.get('initial_cause', '')
            if initial:
                wrapped = textwrap.fill(f"  Initial: {initial}", width=max_width, subsequent_indent="           ")
                lines.append(wrapped)

            effects = chain.get('intermediate_effects', [])
            if effects:
                lines.append("  Effects:")
                for j, effect in enumerate(effects, 1):
                    wrapped = textwrap.fill(f"    {j}. {effect}", width=max_width, subsequent_indent="       ")
                    lines.append(wrapped)

            final = chain.get('final_outcome', '')
            if final:
                wrapped = textwrap.fill(f"  Final: {final}", width=max_width, subsequent_indent="         ")
                lines.append(wrapped)

            uncertainties = chain.get('key_uncertainties', [])
            if uncertainties:
                lines.append("  Uncertainties:")
                for unc in uncertainties:
                    wrapped = textwrap.fill(f"    - {unc}", width=max_width, subsequent_indent="      ")
                    lines.append(wrapped)

            lines.append("")

        lines.append("")

    def _format_event_risks(
        self,
        lines: List[str],
        forecast_data: Dict[str, Any],
        max_width: int
    ) -> None:
        """Format event risk categorization section (Rumsfeld framework)"""
        lines.append("-" * max_width)
        lines.append("5. EVENT RISK CATEGORIZATION")
        lines.append("-" * max_width)
        lines.append("")

        event_risks = forecast_data.get('event_risks', {})

        # Known Knowns
        known_knowns = event_risks.get('known_knowns', [])
        if known_knowns:
            lines.append("KNOWN KNOWNS (Scheduled/confirmed events):")
            for event in known_knowns[:5]:  # Limit to top 5
                event_name = event.get('event', 'Unknown event')
                date = event.get('date', 'TBD')
                lines.append(f"  - {event_name} ({date})")

                certainty_basis = event.get('certainty_basis', '')
                if certainty_basis:
                    wrapped = textwrap.fill(f"    Basis: {certainty_basis}", width=max_width, subsequent_indent="           ")
                    lines.append(wrapped)

                impact = event.get('impact', '')
                if impact:
                    wrapped = textwrap.fill(f"    Impact: {impact}", width=max_width, subsequent_indent="            ")
                    lines.append(wrapped)

            lines.append("")

        # Known Unknowns
        known_unknowns = event_risks.get('known_unknowns', [])
        if known_unknowns:
            lines.append("KNOWN UNKNOWNS (Recognized but uncertain):")
            for event in known_unknowns[:5]:  # Limit to top 5
                uncertainty = event.get('uncertainty', 'Unknown uncertainty')
                lines.append(f"  - {uncertainty}")

                outcomes = event.get('possible_outcomes', [])
                if outcomes:
                    lines.append("    Possible outcomes:")
                    for outcome in outcomes[:3]:
                        wrapped = textwrap.fill(f"      • {outcome}", width=max_width, subsequent_indent="        ")
                        lines.append(wrapped)

                factors = event.get('factors_affecting_outcome', [])
                if factors:
                    lines.append("    Key factors:")
                    for factor in factors[:3]:
                        wrapped = textwrap.fill(f"      • {factor}", width=max_width, subsequent_indent="        ")
                        lines.append(wrapped)

            lines.append("")

        # Unknown Unknowns
        unknown_unknowns = event_risks.get('unknown_unknowns', [])
        if unknown_unknowns:
            lines.append("UNKNOWN UNKNOWNS (Speculative risks):")
            for event in unknown_unknowns[:3]:  # Limit to top 3
                signal = event.get('weak_signal', 'Speculative risk')
                lines.append(f"  - {signal}")

                plausibility = event.get('why_plausible', '')
                if plausibility:
                    wrapped = textwrap.fill(f"    Why plausible: {plausibility}", width=max_width, subsequent_indent="                   ")
                    lines.append(wrapped)

                impact = event.get('potential_impact', '')
                if impact:
                    wrapped = textwrap.fill(f"    If occurs: {impact}", width=max_width, subsequent_indent="               ")
                    lines.append(wrapped)

            lines.append("")

    def save_html_report(self, result: Dict[str, Any]) -> Path:
        """
        Generate and save HTML report

        Args:
            result: Forecast result dictionary with run_id and forecasts

        Returns:
            Path to saved HTML file
        """
        # Simple HTML template for MVP
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<title>InsightWeaver Forecast Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }",
            "h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }",
            "h2 { color: #34495e; margin-top: 30px; border-bottom: 2px solid #bdc3c7; padding-bottom: 5px; }",
            "h3 { color: #7f8c8d; }",
            ".metadata { background: #ecf0f1; padding: 15px; border-radius: 5px; margin-bottom: 20px; }",
            ".scenario { background: #e8f4f8; padding: 15px; margin: 15px 0; border-left: 4px solid #3498db; }",
            ".trend { background: #e8f8e8; padding: 15px; margin: 15px 0; border-left: 4px solid #27ae60; }",
            ".risk { background: #fff5e6; padding: 15px; margin: 15px 0; border-left: 4px solid #f39c12; }",
            ".chain { background: #f4e8f8; padding: 15px; margin: 15px 0; border-left: 4px solid #9b59b6; }",
            "ul { line-height: 1.6; }",
            ".confidence { font-weight: bold; color: #2980b9; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>InsightWeaver Long-Term Forecast</h1>"
        ]

        # Add forecasts
        for forecast in result.get('forecasts', []):
            forecast_data = forecast['forecast_data']

            html_parts.append(f"<div class='metadata'>")
            html_parts.append(f"<strong>Time Horizon:</strong> {forecast['time_horizon']}<br>")
            html_parts.append(f"<strong>Target Date:</strong> {forecast['target_date']}")
            html_parts.append("</div>")

            # Trends
            html_parts.append("<h2>Trend Extrapolations</h2>")
            for trend in forecast_data.get('trend_extrapolations', []):
                html_parts.append("<div class='trend'>")
                html_parts.append(f"<h3>{trend.get('trend', 'N/A')}</h3>")
                html_parts.append(f"<p><strong>Current State:</strong> {trend.get('current_state', '')}</p>")
                html_parts.append(f"<p><strong>Projected Outcome:</strong> {trend.get('projected_outcome', '')}</p>")

                uncertainties = trend.get('uncertainties', [])
                if uncertainties:
                    html_parts.append("<p><strong>Uncertainties:</strong></p><ul>")
                    for unc in uncertainties:
                        html_parts.append(f"<li>{unc}</li>")
                    html_parts.append("</ul>")

                html_parts.append("</div>")

            # Scenarios
            html_parts.append("<h2>Scenario Modeling</h2>")
            for scenario in forecast_data.get('scenarios', []):
                html_parts.append("<div class='scenario'>")
                html_parts.append(f"<h3>[{scenario.get('type', '').upper()}] {scenario.get('name', 'Unnamed')}</h3>")

                plausibility = scenario.get('plausibility', '')
                if plausibility:
                    html_parts.append(f"<p><strong>Plausibility:</strong> {plausibility}</p>")

                html_parts.append("<p><strong>Predictions:</strong></p><ul>")
                for pred in scenario.get('predictions', [])[:5]:
                    html_parts.append(f"<li>{pred}</li>")
                html_parts.append("</ul>")
                html_parts.append("</div>")

            # Causal Chains
            html_parts.append("<h2>Causal Chain Analysis</h2>")
            for chain in forecast_data.get('causal_chains', []):
                html_parts.append("<div class='chain'>")
                html_parts.append(f"<h3>{chain.get('chain_name', 'Chain')}</h3>")
                html_parts.append(f"<p><strong>Initial Cause:</strong> {chain.get('initial_cause', '')}</p>")
                html_parts.append("<p><strong>Effects:</strong></p><ol>")
                for effect in chain.get('intermediate_effects', []):
                    html_parts.append(f"<li>{effect}</li>")
                html_parts.append("</ol>")
                html_parts.append(f"<p><strong>Final Outcome:</strong> {chain.get('final_outcome', '')}</p>")
                html_parts.append("</div>")

            # Event Risks
            html_parts.append("<h2>Event Risk Categorization</h2>")
            event_risks = forecast_data.get('event_risks', {})

            html_parts.append("<div class='risk'>")
            html_parts.append("<h3>Known Knowns</h3><ul>")
            for event in event_risks.get('known_knowns', [])[:5]:
                html_parts.append(f"<li><strong>{event.get('event', 'N/A')}</strong> - {event.get('date', 'TBD')}")
                if event.get('certainty_basis'):
                    html_parts.append(f"<br><em>Basis: {event.get('certainty_basis')}</em>")
                html_parts.append("</li>")
            html_parts.append("</ul>")

            html_parts.append("<h3>Known Unknowns</h3><ul>")
            for event in event_risks.get('known_unknowns', [])[:5]:
                html_parts.append(f"<li><strong>{event.get('uncertainty', 'N/A')}</strong>")
                outcomes = event.get('possible_outcomes', [])
                if outcomes:
                    html_parts.append("<br>Possible outcomes: " + ", ".join(outcomes[:3]))
                html_parts.append("</li>")
            html_parts.append("</ul>")

            html_parts.append("<h3>Unknown Unknowns</h3><ul>")
            for event in event_risks.get('unknown_unknowns', [])[:3]:
                html_parts.append(f"<li><strong>{event.get('weak_signal', 'N/A')}</strong>")
                if event.get('why_plausible'):
                    html_parts.append(f"<br><em>Why plausible: {event.get('why_plausible')}</em>")
                html_parts.append("</li>")
            html_parts.append("</ul>")
            html_parts.append("</div>")

        # Footer
        html_parts.append(f"<hr><p style='color: #7f8c8d; font-size: 0.9em;'>Generated by InsightWeaver on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
        html_parts.append("</body></html>")

        # Save to file
        output_dir = Path("data/forecasts")
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"forecast_{result['run_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = output_dir / filename

        filepath.write_text("\n".join(html_parts))

        return filepath
