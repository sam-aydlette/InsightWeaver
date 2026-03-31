"""
Brief Command - Intelligence Brief Generation
Preserves all existing InsightWeaver functionality
"""

import asyncio
import logging

import click

from ..config.settings import settings
from ..database.connection import create_tables
from ..feed_manager import setup_feeds
from ..pipeline.orchestrator import run_pipeline
from .brief_formatter import clean_citations
from .colors import accent, header, muted, warning
from .loading import loading
from .output import get_output_manager, is_debug_mode

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (from main.py)
# ============================================================================


async def run_fetch_only():
    """Run only RSS fetching"""
    from ..rss.parallel_fetcher import fetch_all_active_feeds

    print("Running RSS feed fetching...")
    results = await fetch_all_active_feeds()
    print(
        f"Fetched {results['total_articles']} articles from {results['successful_feeds']}/{results['total_feeds']} feeds"
    )
    return results


def setup_database():
    """Initialize database and load feeds"""
    print("Setting up database...")
    create_tables()
    print("Database tables created")

    print("Loading RSS feeds...")
    fm = setup_feeds()
    stats = fm.get_feed_statistics()
    print(
        f"Loaded {stats['database']['active_feeds']} active feeds across {len(stats['database']['categories'])} categories"
    )


# ============================================================================
# Click Command Group
# ============================================================================


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--hours", type=int, default=24, help="Look back N hours for analysis (default: 24)")
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Compact output (situation titles only, for scripts/automation)",
)
@click.option(
    "--cybersecurity",
    "-cs",
    "filter_cybersecurity",
    is_flag=True,
    help="Filter to cybersecurity-related articles only",
)
@click.option(
    "--ai", "-ai", "filter_ai", is_flag=True, help="Filter to AI/ML-related articles only"
)
@click.option("--local", "-l", "filter_local", is_flag=True, help="Filter to local news only")
@click.option(
    "--state", "-s", "filter_state", is_flag=True, help="Filter to state/regional news only"
)
@click.option(
    "--national", "-n", "filter_national", is_flag=True, help="Filter to national news only"
)
@click.option(
    "--global", "-g", "filter_global", is_flag=True, help="Filter to global/international news only"
)
def brief_group(
    ctx,
    hours,
    quiet,
    filter_cybersecurity,
    filter_ai,
    filter_local,
    filter_state,
    filter_national,
    filter_global,
):
    """
    Run intelligence brief pipeline and generate report

    Fetches RSS feeds, analyzes content with Claude, and generates
    intelligence reports tailored to your location and interests.

    You can filter by topic (e.g., --cybersecurity) and/or scope (e.g., --local).
    Multiple filters combine with AND logic: --cybersecurity --local shows only local cybersecurity news.
    """
    if ctx.invoked_subcommand is None:
        # Check for API key
        if not settings.anthropic_api_key:
            click.echo(warning("Warning: ANTHROPIC_API_KEY not configured"))
            click.echo(muted("Brief generation requires Claude API access"))
            raise click.Abort()

        # Build topic_filters dict from flags
        topic_filters = {}

        # Topic filters (from professional_domains)
        topics = []
        if filter_cybersecurity:
            topics.append("cybersecurity")
        if filter_ai:
            topics.append("ai/ml")

        if topics:
            topic_filters["topics"] = topics

        # Scope filters (geographic)
        scopes = []
        if filter_local:
            scopes.append("local")
        if filter_state:
            scopes.append("state")
        if filter_national:
            scopes.append("national")
        if filter_global:
            scopes.append("global")

        if scopes:
            topic_filters["scopes"] = scopes

        # Store in context for subcommands
        ctx.ensure_object(dict)
        ctx.obj["topic_filters"] = topic_filters

        debug = is_debug_mode()
        output_mgr = get_output_manager()

        # Build loading message based on filters
        if topic_filters:
            filter_desc = []
            if topics:
                filter_desc.append(f"{', '.join(topics)}")
            if scopes:
                filter_desc.append(f"{', '.join(scopes)}")
            loading_msg = f"Generating {' '.join(filter_desc)} brief"
        else:
            loading_msg = "Generating intelligence brief"

        # Run pipeline (fetch, deduplicate, filter, synthesize)
        async def run_brief():
            pipeline_result = await run_pipeline(
                prioritize_hours=hours, topic_filters=topic_filters
            )

            # Extract synthesis result from pipeline
            synthesis_stage = pipeline_result.get("stages", {}).get("synthesis", {})
            report_result = {
                "success": synthesis_stage.get("status") == "success",
                "articles_analyzed": synthesis_stage.get("articles_analyzed", 0),
                "synthesis_data": synthesis_stage.get("synthesis_data", {}),
                "synthesis_id": synthesis_stage.get("synthesis_id"),
            }

            return {"pipeline": pipeline_result, "report": report_result}

        with loading(loading_msg, debug=debug), output_mgr.suppress_output():
            result = asyncio.run(run_brief())

        # Display results
        report_path = None
        if result:
            pipeline_summary = result.get("pipeline", {}).get("summary", {})
            report_result = result.get("report", {})

            # Check if filters resulted in 0 articles
            articles_analyzed = report_result.get("articles_analyzed", 0)
            articles_fetched = pipeline_summary.get("articles_fetched", 0)

            if topic_filters and articles_analyzed == 0 and articles_fetched > 0:
                # Filters were too restrictive
                click.echo("\n" + warning("!" * 80))
                click.echo(warning("NO ARTICLES MATCHED YOUR FILTERS"))
                click.echo(warning("!" * 80))
                click.echo(muted(f"\nFetched {articles_fetched} articles, but none matched:"))
                if "topics" in topic_filters:
                    click.echo(f"  Topics: {', '.join(topic_filters['topics'])}")
                if "scopes" in topic_filters:
                    click.echo(f"  Scopes: {', '.join(topic_filters['scopes'])}")
                click.echo("\nSuggestions:")
                click.echo("  • Try expanding the time window: --hours 48 or --hours 168")
                click.echo("  • Use fewer filters (remove -s or -cs)")
                click.echo("  • Try different filter combinations")
                click.echo("  • Run without filters to see all available content")
                click.echo("=" * 80)
            elif report_result.get("success") and articles_analyzed > 0:
                synthesis_data = report_result.get("synthesis_data", {})
                situations = synthesis_data.get("situations", [])
                metadata = synthesis_data.get("metadata", {})

                # Generate HTML report
                from .html_report import save_html_report

                report_path = save_html_report(synthesis_data)

                # Terminal summary (always shown)
                click.echo()
                if situations:
                    click.echo(header("Situations analyzed:"))
                    for i, s in enumerate(situations, 1):
                        title = clean_citations(s.get("title", "Untitled"))
                        click.echo(f"  {accent(f'{i}.')} {title}")

                thin = synthesis_data.get("thin_coverage", [])
                if thin:
                    click.echo(muted(f"\n+ {len(thin)} topics with thin coverage"))

                click.echo(
                    muted(
                        f"\nArticles: {articles_analyzed} | "
                        f"Clusters: {metadata.get('clusters_total', 0)}"
                    )
                )

                if not quiet:
                    click.echo(f"\nReport saved: {accent(str(report_path))}")

            # Pipeline summary
            click.echo()
            click.echo(muted(f"Duration: {pipeline_summary.get('duration_seconds', 0):.1f}s"))

            # Print profiling report in debug mode
            if debug:
                from ..utils.profiler import get_profiler

                profiler = get_profiler()
                profiler.print_summary()

            # Interactive frame validation (only in TTY, after successful brief)
            if (
                report_result.get("success")
                and articles_analyzed > 0
                and click.get_text_stream("stdin").isatty()
            ):
                from .frames import run_frame_validation_loop

                run_frame_validation_loop()

                # Open HTML report in browser after frame validation
                if report_path and not quiet:
                    import webbrowser

                    click.echo(f"\nOpening report in browser: {accent(str(report_path))}")
                    webbrowser.open(f"file://{report_path}")


# ============================================================================
# Subcommands
# ============================================================================


@brief_group.command(name="setup")
def setup_cmd():
    """Setup database and load RSS feeds"""
    setup_database()


@brief_group.command(name="fetch")
def fetch_cmd():
    """Only fetch RSS feeds (no analysis)"""
    debug = is_debug_mode()
    output_mgr = get_output_manager()

    with loading("Fetching RSS feeds", debug=debug), output_mgr.suppress_output():
        result = asyncio.run(run_fetch_only())

    if result:
        click.echo(
            f"\n✓ Fetched {result['total_articles']} articles from {result['successful_feeds']}/{result['total_feeds']} feeds"
        )
