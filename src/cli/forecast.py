"""
Forecast CLI Command
Long-term trend forecasting interface for InsightWeaver
MVP: 1-year horizon only
"""

import asyncio
import logging

import click

from ..forecast.orchestrator import ForecastOrchestrator
from ..utils.profile_loader import get_user_profile
from .forecast_verifier import (
    format_forecast_trust_section,
    verify_forecast_aggregate,
    verify_forecast_horizon,
)
from .loading import loading
from .output import is_debug_mode

logger = logging.getLogger(__name__)


@click.command()
@click.option('--horizon', type=str, default=None,
              help='Time horizon(s): 6mo, 1yr, 3yr, 5yr, or custom (e.g., "18 months"). Default: all horizons')
@click.option('--scenarios', type=int, default=0,
              help='Number of detailed scenarios to generate (0 = skip, 3 = standard)')
@click.option('--full', is_flag=True,
              help='Show full detailed analysis (default: executive briefing)')
@click.option('--no-verify', 'no_verify', is_flag=True,
              help='Skip trust verification of AI output')
@click.option('--cybersecurity', '-cs', 'filter_cybersecurity', is_flag=True,
              help='Filter to cybersecurity topics only')
@click.option('--ai', '-ai', 'filter_ai', is_flag=True,
              help='Filter to AI/ML topics only')
@click.option('--local', '-l', 'filter_local', is_flag=True,
              help='Filter to local news only')
@click.option('--state', '-s', 'filter_state', is_flag=True,
              help='Filter to state news only')
@click.option('--national', '-n', 'filter_national', is_flag=True,
              help='Filter to national news only')
@click.option('--global', '-g', 'filter_global', is_flag=True,
              help='Filter to global/international news only')
@click.pass_context
def forecast_command(
    ctx,
    horizon,
    scenarios,
    full,
    no_verify,
    filter_cybersecurity,
    filter_ai,
    filter_local,
    filter_state,
    filter_national,
    filter_global
):
    """
    Generate long-term trend forecasts

    Analyzes historical data and authoritative sources to predict trends,
    scenarios, and key events across multiple time horizons.

    Output formats:
    - Executive Briefing (default): Condensed 1-2 slide summary
    - Full Analysis (--full): Detailed 5-part analysis

    Uses 5 analysis types:
    - Trend Extrapolation
    - Scenario Modeling
    - Pattern Recognition
    - Causal Chain Analysis
    - Event Risk Categorization

    Examples:
      insightweaver forecast                    (executive briefing, all horizons)
      insightweaver forecast --full             (full detailed analysis)
      insightweaver forecast --horizon 1yr      (1-year executive briefing)
      insightweaver forecast --horizon "18mo"   (custom 18-month)
      insightweaver forecast --scenarios 3      (include detailed scenarios)
      insightweaver forecast -cs --horizon 3yr  (3-year cybersecurity)
    """
    # Build topic filters
    topic_filters = _build_topic_filters(
        filter_cybersecurity,
        filter_ai,
        filter_local,
        filter_state,
        filter_national,
        filter_global
    )

    # Run forecast with loading indicator
    debug = is_debug_mode()

    # Determine loading message
    if horizon:
        loading_msg = f"Generating {horizon} forecast"
    else:
        loading_msg = "Generating multi-horizon forecasts"

    with loading(loading_msg, debug=debug):
        asyncio.run(_run_forecast(horizon, scenarios, full, no_verify, topic_filters))


async def _run_forecast(
    horizon: str | None,
    scenarios: int,
    full: bool,
    no_verify: bool,
    topic_filters: dict | None
):
    """
    Execute forecast generation using orchestrator

    Args:
        horizon: Horizon string or None for all horizons
        scenarios: Number of scenarios to generate
        full: If True, show full detailed analysis; if False, show executive briefing
        no_verify: If True, skip trust verification
        topic_filters: Topic/scope filters dict
    """
    try:
        # Determine horizons
        if horizon:
            horizons = [horizon]
        else:
            horizons = None  # Orchestrator will use all default horizons

        # Initialize orchestrator
        user_profile = get_user_profile()
        orchestrator = ForecastOrchestrator(
            user_profile=user_profile,
            topic_filters=topic_filters
        )

        if is_debug_mode():
            click.echo(f"Initialized orchestrator with filters: {topic_filters}")

        # Run forecast
        result = await orchestrator.run_forecast(
            horizons=horizons,
            scenario_count=scenarios
        )

        click.echo(f"\n✓ Generated {result['successful_horizons']} forecast(s) successfully!")
        click.echo()

        # Display forecasts using appropriate formatter
        if full:
            # Full detailed analysis
            from ..forecast.formatter import ForecastFormatter
            formatter = ForecastFormatter()

            for forecast in result['forecasts']:
                formatted_output = formatter.format_forecast(forecast)
                click.echo(formatted_output)

                # Trust verification for this horizon (unless --no-verify)
                if not no_verify:
                    horizon_name = forecast.get('horizon', 'unknown')
                    # Extract natural language content for verification
                    # (trend description + scenario descriptions if present)
                    trend_description = forecast.get('trend_description', '')
                    scenarios_text = ''
                    if forecast.get('scenarios'):
                        scenarios_text = '\n'.join([s.get('description', '') for s in forecast['scenarios']])

                    horizon_text = f"{trend_description}\n\n{scenarios_text}".strip()

                    if horizon_text:
                        click.echo()  # Add spacing
                        # We're inside async context, can't use loading context manager easily
                        # So we'll show a progress message using original stderr to bypass output suppression
                        import sys
                        sys.__stderr__.write(f"⠋ Verifying {horizon_name} forecast for trustworthiness...\r")
                        sys.__stderr__.flush()
                        trust_analysis = await verify_forecast_horizon(horizon_text, horizon_name)
                        sys.__stderr__.write(" " * 80 + "\r")  # Clear the line
                        sys.__stderr__.flush()
                        trust_section = format_forecast_trust_section(trust_analysis, horizon_name)
                        if trust_section:
                            click.echo(trust_section)

            # Save HTML report
            report_path = formatter.save_html_report(result)
        else:
            # Executive briefing (default)
            from ..forecast.executive_formatter import ExecutiveForecastFormatter
            from ..forecast.formatter import ForecastFormatter

            # Save full HTML report (still contains all detail)
            full_formatter = ForecastFormatter()
            report_path = full_formatter.save_html_report(result)

            # Use executive formatter for terminal output
            exec_formatter = ExecutiveForecastFormatter()
            briefing = exec_formatter.format_executive_briefing(result['forecasts'], report_path)
            click.echo(briefing)

            # Trust verification for executive summary (unless --no-verify)
            if not no_verify:
                # Extract all natural language content from forecasts for aggregate verification
                all_trend_descriptions = []
                all_scenarios = []

                for forecast in result['forecasts']:
                    trend_description = forecast.get('trend_description', '')
                    if trend_description:
                        all_trend_descriptions.append(trend_description)

                    if forecast.get('scenarios'):
                        for scenario in forecast['scenarios']:
                            scenario_desc = scenario.get('description', '')
                            if scenario_desc:
                                all_scenarios.append(scenario_desc)

                executive_text = '\n\n'.join(all_trend_descriptions + all_scenarios).strip()

                if executive_text:
                    click.echo()  # Add spacing
                    import sys
                    sys.__stderr__.write("⠋ Verifying forecast executive summary for trustworthiness...\r")
                    sys.__stderr__.flush()
                    trust_analysis = await verify_forecast_aggregate(executive_text)
                    sys.__stderr__.write(" " * 80 + "\r")  # Clear the line
                    sys.__stderr__.flush()
                    trust_section = format_forecast_trust_section(trust_analysis)
                    if trust_section:
                        click.echo(trust_section)

        click.echo()
        click.echo(f"✓ HTML report saved: {report_path}")

    except Exception as e:
        logger.error(f"Forecast generation failed: {e}", exc_info=True)
        click.echo(f"✗ Error: Forecast generation failed: {str(e)}")
        # Orchestrator handles run status updates internally


def _build_topic_filters(
    filter_cybersecurity: bool,
    filter_ai: bool,
    filter_local: bool,
    filter_state: bool,
    filter_national: bool,
    filter_global: bool
) -> dict | None:
    """
    Build topic filters dictionary from CLI flags

    Args:
        filter_cybersecurity: Cybersecurity filter flag
        filter_ai: AI filter flag
        filter_local: Local scope filter flag
        filter_state: State scope filter flag
        filter_national: National scope filter flag
        filter_global: Global scope filter flag

    Returns:
        Topic filters dict or None if no filters active
    """
    topics = []
    if filter_cybersecurity:
        topics.append('cybersecurity')
    if filter_ai:
        topics.append('ai')

    scopes = []
    if filter_local:
        scopes.append('local')
    if filter_state:
        scopes.append('state')
    if filter_national:
        scopes.append('national')
    if filter_global:
        scopes.append('global')

    # Only return filters if at least one is active
    if topics or scopes:
        return {
            'topics': topics,
            'scopes': scopes
        }

    return None
