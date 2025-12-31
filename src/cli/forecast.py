"""
Forecast CLI Command
Long-term trend forecasting interface for InsightWeaver
MVP: 1-year horizon only
"""

import click
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict

from ..forecast.orchestrator import ForecastOrchestrator
from ..database.connection import get_db
from ..database.models import ForecastRun
from ..utils.profile_loader import get_user_profile
from .output import is_debug_mode

logger = logging.getLogger(__name__)


@click.command()
@click.option('--horizon', type=str, default=None,
              help='Time horizon(s): 6mo, 1yr, 3yr, 5yr, or custom (e.g., "18 months"). Default: all horizons')
@click.option('--scenarios', type=int, default=0,
              help='Number of detailed scenarios to generate (0 = skip, 3 = standard)')
@click.option('--full', is_flag=True,
              help='Show full detailed analysis (default: executive briefing)')
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

    # Run forecast
    asyncio.run(_run_forecast(horizon, scenarios, full, topic_filters))


async def _run_forecast(
    horizon: Optional[str],
    scenarios: int,
    full: bool,
    topic_filters: Optional[Dict]
):
    """
    Execute forecast generation using orchestrator

    Args:
        horizon: Horizon string or None for all horizons
        scenarios: Number of scenarios to generate
        full: If True, show full detailed analysis; if False, show executive briefing
        topic_filters: Topic/scope filters dict
    """
    try:
        # Determine horizons
        if horizon:
            horizons = [horizon]
            click.echo(f"Generating {horizon} forecast...")
        else:
            horizons = None  # Orchestrator will use all default horizons
            click.echo("Generating multi-horizon forecasts (6mo, 1yr, 3yr, 5yr)...")

        click.echo()

        # Initialize orchestrator
        user_profile = get_user_profile()
        orchestrator = ForecastOrchestrator(
            user_profile=user_profile,
            topic_filters=topic_filters
        )

        if is_debug_mode():
            click.echo(f"Initialized orchestrator with filters: {topic_filters}")

        # Run forecast
        if horizons and len(horizons) == 1:
            click.echo("Curating historical context...")
            click.echo("Analyzing trends and generating forecast...")
            click.echo("This may take 30-90 seconds...")
        else:
            click.echo("Generating forecasts for multiple horizons...")
            click.echo("This may take several minutes...")

        click.echo()

        result = await orchestrator.run_forecast(
            horizons=horizons,
            scenario_count=scenarios
        )

        click.echo(f"✓ Generated {result['successful_horizons']} forecast(s) successfully!")
        click.echo()

        # Display forecasts using appropriate formatter
        if full:
            # Full detailed analysis
            from ..forecast.formatter import ForecastFormatter
            formatter = ForecastFormatter()

            for forecast in result['forecasts']:
                formatted_output = formatter.format_forecast(forecast)
                click.echo(formatted_output)

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
) -> Optional[Dict]:
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
