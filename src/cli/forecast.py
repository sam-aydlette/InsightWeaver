"""
Forecast CLI Command
Certainty-based forecasting interface for InsightWeaver
"""

import asyncio
import logging

import click

from ..forecast.orchestrator import ForecastOrchestrator
from ..utils.profile_loader import get_user_profile
from .ascii_art import render_forecast_art, should_show_art
from .colors import accent, error, header, muted
from .loading import loading
from .output import is_debug_mode

logger = logging.getLogger(__name__)


@click.command()
@click.option("--full", is_flag=True, help="Show full detailed analysis (default: summary)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress ASCII art (for scripts/automation)")
@click.option(
    "--cybersecurity",
    "-cs",
    "filter_cybersecurity",
    is_flag=True,
    help="Filter to cybersecurity topics only",
)
@click.option("--ai", "-ai", "filter_ai", is_flag=True, help="Filter to AI/ML topics only")
@click.option("--local", "-l", "filter_local", is_flag=True, help="Filter to local news only")
@click.option("--state", "-s", "filter_state", is_flag=True, help="Filter to state news only")
@click.option(
    "--national", "-n", "filter_national", is_flag=True, help="Filter to national news only"
)
@click.option(
    "--global", "-g", "filter_global", is_flag=True, help="Filter to global/international news only"
)
@click.pass_context
def forecast_command(
    _ctx,
    full,
    quiet,
    filter_cybersecurity,
    filter_ai,
    filter_local,
    filter_state,
    filter_national,
    filter_global,
):
    """
    Generate certainty-based forecasts

    Analyzes historical data and current trends to generate forecasts
    organized by certainty level:

    - Known Knowns: Certain or near-certain events
    - Known Unknowns: Evidence-based projections
    - Unknown Unknowns: Weak signal speculation

    Each forecast includes its own timeline.

    Examples:
      insightweaver forecast                  (summary output)
      insightweaver forecast --full           (full detailed analysis)
      insightweaver forecast -cs              (cybersecurity focus)
      insightweaver forecast -l               (local focus)
    """
    # Build topic filters
    topic_filters = _build_topic_filters(
        filter_cybersecurity, filter_ai, filter_local, filter_state, filter_national, filter_global
    )

    # Run forecast with loading indicator
    debug = is_debug_mode()
    loading_msg = "Generating certainty-based forecast"

    with loading(loading_msg, debug=debug):
        asyncio.run(_run_forecast(full, quiet, topic_filters))


async def _run_forecast(
    full: bool,
    quiet: bool,
    topic_filters: dict | None,
):
    """
    Execute forecast generation using orchestrator

    Args:
        full: If True, show full detailed analysis; if False, show summary
        quiet: If True, suppress ASCII art
        topic_filters: Topic/scope filters dict
    """
    try:
        # Initialize orchestrator
        user_profile = get_user_profile()
        orchestrator = ForecastOrchestrator(user_profile=user_profile, topic_filters=topic_filters)

        if is_debug_mode():
            click.echo(muted(f"Initialized orchestrator with filters: {topic_filters}"))

        # Run forecast
        result = await orchestrator.run_forecast()

        # Save reports (HTML and JSON)
        from ..forecast.formatter import ForecastFormatter

        formatter = ForecastFormatter()
        html_path = formatter.save_html_report(result)
        json_path = formatter.save_json_report(result)

        # Show ASCII art (unless --quiet or non-TTY)
        if should_show_art(quiet):
            click.echo(render_forecast_art("Forecast complete"))

        # Display forecasts based on mode
        forecast = result.get("forecast", {})
        forecast_data = forecast.get("forecast_data", {})

        if full:
            # Full terminal output
            formatted_output = formatter.format_forecast(forecast)
            click.echo(formatted_output)
        else:
            # Summary output: 1 forecast per category
            click.echo("\n" + header("Forecast Summary:"))
            click.echo("")

            # Known Knowns - show first one
            known_knowns = forecast_data.get("known_knowns", [])
            click.echo(header("  Certain:"))
            if known_knowns:
                item = known_knowns[0]
                forecast_text = item.get("forecast", "No forecast")
                timeline = item.get("timeline", "Unknown")
                click.echo(f"    {accent('*')} {forecast_text}")
                click.echo(f"      {muted('Timeline:')} {timeline}")
            else:
                click.echo(f"    {muted('No certain forecasts identified')}")
            click.echo("")

            # Known Unknowns - show first one
            known_unknowns = forecast_data.get("known_unknowns", [])
            click.echo(header("  Likely:"))
            if known_unknowns:
                item = known_unknowns[0]
                forecast_text = item.get("forecast", "No forecast")
                timeline = item.get("timeline", "Unknown")
                click.echo(f"    {accent('*')} {forecast_text}")
                click.echo(f"      {muted('Timeline:')} {timeline}")
            else:
                click.echo(f"    {muted('No evidence-based projections identified')}")
            click.echo("")

            # Unknown Unknowns - show first one
            unknown_unknowns = forecast_data.get("unknown_unknowns", [])
            click.echo(header("  Possible:"))
            if unknown_unknowns:
                item = unknown_unknowns[0]
                forecast_text = item.get("forecast", "No forecast")
                timeline = item.get("timeline", "Unknown")
                click.echo(f"    {accent('*')} {forecast_text}")
                click.echo(f"      {muted('Timeline:')} {timeline}")
            else:
                click.echo(f"    {muted('No weak signal projections identified')}")

        # Reports saved section
        click.echo("\n" + header("Reports saved:"))
        click.echo(f"  {muted('HTML:')} {accent(str(html_path))}")
        click.echo(f"  {muted('JSON:')} {accent(str(json_path))}")

    except Exception as e:
        logger.error(f"Forecast generation failed: {e}", exc_info=True)
        click.echo(error(f"Error: Forecast generation failed: {str(e)}"))


def _build_topic_filters(
    filter_cybersecurity: bool,
    filter_ai: bool,
    filter_local: bool,
    filter_state: bool,
    filter_national: bool,
    filter_global: bool,
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
        topics.append("cybersecurity")
    if filter_ai:
        topics.append("ai")

    scopes = []
    if filter_local:
        scopes.append("local")
    if filter_state:
        scopes.append("state")
    if filter_national:
        scopes.append("national")
    if filter_global:
        scopes.append("global")

    # Only return filters if at least one is active
    if topics or scopes:
        return {"topics": topics, "scopes": scopes}

    return None
