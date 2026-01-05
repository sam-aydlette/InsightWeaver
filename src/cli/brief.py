"""
Brief Command - Intelligence Brief Generation
Preserves all existing InsightWeaver functionality
"""
import asyncio
import logging
from datetime import datetime

import click

from ..config.settings import settings
from ..database.connection import create_tables
from ..feed_manager import setup_feeds
from ..pipeline.orchestrator import run_pipeline
from .brief_formatter import BriefFormatter
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
    print(f"Fetched {results['total_articles']} articles from {results['successful_feeds']}/{results['total_feeds']} feeds")
    return results


async def run_analysis_only():
    """Run analysis on existing articles using context-driven approach"""
    print("Running article analysis...")
    print("⚠️ Analysis functionality being refactored to context-engineering approach")
    return {"status": "pending_refactor"}


async def run_collectors(force=False, collector_name=None):
    """Run API data collectors"""
    from ..collectors.manager import CollectorManager

    print("\n" + "=" * 60)
    print("Running Data Collectors")
    print("=" * 60 + "\n")

    manager = CollectorManager()

    if collector_name:
        print(f"Running specific collector: {collector_name}")
        result = manager.run_specific_collector(collector_name)
        print(f"\n✓ Collector '{collector_name}' completed")
        print(f"  • New items: {result.get('new_items', 0)}")
        print(f"  • Duplicates skipped: {result.get('duplicates_skipped', 0)}")
        return result
    else:
        print(f"Running all {'collectors (forced)' if force else 'due collectors'}...")
        summary = manager.collect_all(force=force)

        print("\n" + "=" * 60)
        print("Collection Summary")
        print("=" * 60)
        print(f"• Total collectors: {summary['total_collectors']}")
        print(f"• Collectors run: {summary['collectors_run']}")
        print(f"• Collectors skipped: {summary['collectors_skipped']}")
        print(f"• Collectors failed: {summary['collectors_failed']}")
        print(f"• Total items collected: {summary['total_items_collected']}")

        if summary['results']:
            print("\nDetailed Results:")
            for name, result in summary['results'].items():
                if result.get('success', True):
                    print(f"  • {name}: {result.get('new_items', 0)} new items")
                else:
                    print(f"  • {name}: FAILED - {result.get('error', 'Unknown error')}")

        print("=" * 60)
        return summary


def show_collector_status():
    """Display status of all collectors"""
    from ..collectors.manager import CollectorManager

    manager = CollectorManager()
    status = manager.get_collection_status()

    if not status:
        print("No collectors configured or no data sources in database")
        return

    print("\n" + "=" * 60)
    print("Collector Status")
    print("=" * 60)

    for name, info in status.items():
        print(f"\n{name}")
        print(f"  • Type: {info['source_type']}")
        print(f"  • Active: {'Yes' if info['is_active'] else 'No'}")
        print(f"  • Last fetched: {info['last_fetched'] or 'Never'}")
        print(f"  • Error count: {info['error_count']}")
        if info['last_error']:
            print(f"  • Last error: {info['last_error'][:100]}...")

    print("=" * 60)


async def test_newsletter():
    """Test newsletter system only"""
    from ..newsletter.newsletter_system import NewsletterSystem

    system = NewsletterSystem()
    return await system.test_system()


async def run_full_pipeline():
    """Run complete pipeline: fetch -> deduplicate -> prioritize -> trends -> newsletter"""
    print("\n" + "=" * 60)
    print("InsightWeaver Full Pipeline")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Step 1: Run RSS feed collection
    results = await run_pipeline(
        max_concurrent=10,
        rate_limit=2.0,
        dedup_hours=24,
        prioritize_hours=48,
        prioritize_limit=None
    )

    # Step 2: Run API data collectors
    print("\n" + "-" * 60)
    print("Running API Data Collectors")
    print("-" * 60 + "\n")

    try:
        from ..collectors.manager import CollectorManager
        collector_manager = CollectorManager()
        collector_summary = collector_manager.collect_all(force=False)

        print(f"✓ Collectors run: {collector_summary['collectors_run']}")
        print(f"  • Items collected: {collector_summary['total_items_collected']}")
        print(f"  • Collectors skipped: {collector_summary['collectors_skipped']}")
        if collector_summary['collectors_failed'] > 0:
            print(f"  ⚠️  Collectors failed: {collector_summary['collectors_failed']}")

        results['collector_summary'] = collector_summary
    except Exception as e:
        print(f"⚠️ Collector run encountered an issue: {e}")
        print("   Continuing with pipeline...")

    if not settings.anthropic_api_key:
        print("\n⚠️ Skipping analysis - no API key configured")

    # Display summary
    summary = results.get("summary", {})
    collector_summary = results.get("collector_summary", {})

    print("\n" + "=" * 60)
    print("Analysis Pipeline Complete")
    print(f"• Articles fetched: {summary.get('articles_fetched', 0)}")
    print(f"• Duplicates removed: {summary.get('duplicates_removed', 0)}")
    print(f"• Articles analyzed: {summary.get('articles_synthesized', 0)}")
    print(f"• Narrative generated: {summary.get('narrative_generated', False)}")
    if collector_summary:
        print(f"• API data collected: {collector_summary.get('total_items_collected', 0)}")
    print(f"• Duration: {summary.get('duration_seconds', 0):.1f}s")
    print("=" * 60)

    # Generate newsletters if analysis was successful
    if summary.get('articles_synthesized', 0) > 0 or summary.get('articles_fetched', 0) > 0:
        print("\n📧 Generating Intelligence Report...")
        print("-" * 40)

        try:
            from ..newsletter.newsletter_system import NewsletterSystem
            newsletter_system = NewsletterSystem()

            print("📊 Generating Intelligence Report...")
            report_result = await newsletter_system.generate_report(hours=24, send_email=True)

            if report_result["success"]:
                print("✅ Report generated successfully")
                print(f"   • Articles analyzed: {report_result['articles_analyzed']}")
                print(f"   • Report type: {report_result['report_type']}")
                if report_result.get("local_saved"):
                    print(f"   • Saved to: {report_result['local_path']}")
                if report_result.get("email_sent"):
                    print("   • Email sent successfully")

            results["report_results"] = report_result

        except Exception as e:
            print(f"⚠️ Report generation encountered an issue: {e}")
            print("   Data collection and analysis completed successfully.")

    else:
        print("\n⚠️ Skipping report generation - no articles or priority items found")

    print("\n" + "=" * 60)
    print("🎉 Complete Pipeline Finished")
    print("=" * 60)

    return results


def setup_database():
    """Initialize database and load feeds"""
    print("Setting up database...")
    create_tables()
    print("✓ Database tables created")

    print("Loading RSS feeds...")
    fm = setup_feeds()
    stats = fm.get_feed_statistics()
    print(f"✓ Loaded {stats['database']['active_feeds']} active feeds across {len(stats['database']['categories'])} categories")


def query_priorities(min_score=0.5, limit=10):
    """Query and display prioritized articles"""
    from ..database.connection import get_db
    from ..database.models import Article

    with get_db() as db:
        articles = db.query(Article).filter(
            Article.priority_score >= min_score
        ).order_by(Article.priority_score.desc()).limit(limit).all()

        if not articles:
            print(f"No articles with priority score >= {min_score}")
            return

        print(f"\nTop {len(articles)} Priority Articles (score >= {min_score}):")
        print("-" * 60)
        for i, article in enumerate(articles, 1):
            print(f"{i}. [{article.priority_score:.2f}] {article.title[:80]}")
            if article.priority_metadata and article.priority_metadata.get('reasoning'):
                print(f"   → {article.priority_metadata['reasoning'][:100]}...")


# ============================================================================
# Click Command Group
# ============================================================================

@click.group(invoke_without_command=True)
@click.pass_context
@click.option('--hours', type=int, default=24, help='Look back N hours for analysis (default: 24)')
@click.option('--email', is_flag=True, help='Send report via email (in addition to saving locally)')
@click.option('--no-verify', 'no_verify', is_flag=True, help='Skip trust verification of AI output')
@click.option('--cybersecurity', '-cs', 'filter_cybersecurity', is_flag=True,
              help='Filter to cybersecurity-related articles only')
@click.option('--ai', '-ai', 'filter_ai', is_flag=True,
              help='Filter to AI/ML-related articles only')
@click.option('--local', '-l', 'filter_local', is_flag=True,
              help='Filter to local news only')
@click.option('--state', '-s', 'filter_state', is_flag=True,
              help='Filter to state/regional news only')
@click.option('--national', '-n', 'filter_national', is_flag=True,
              help='Filter to national news only')
@click.option('--global', '-g', 'filter_global', is_flag=True,
              help='Filter to global/international news only')
def brief_group(ctx, hours, email, no_verify, filter_cybersecurity, filter_ai, filter_local, filter_state, filter_national, filter_global):
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
            click.echo("⚠️  Warning: ANTHROPIC_API_KEY not configured")
            click.echo("Brief generation requires Claude API access")
            raise click.Abort()

        # Build topic_filters dict from flags
        topic_filters = {}

        # Topic filters (from professional_domains)
        topics = []
        if filter_cybersecurity:
            topics.append('cybersecurity')
        if filter_ai:
            topics.append('ai/ml')

        if topics:
            topic_filters['topics'] = topics

        # Scope filters (geographic)
        scopes = []
        if filter_local:
            scopes.append('local')
        if filter_state:
            scopes.append('state')
        if filter_national:
            scopes.append('national')
        if filter_global:
            scopes.append('global')

        if scopes:
            topic_filters['scopes'] = scopes

        # Store in context for subcommands
        ctx.ensure_object(dict)
        ctx.obj['topic_filters'] = topic_filters

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

        # Run pipeline and generate report
        async def run_brief():
            # Step 1: Run pipeline (fetch, deduplicate, filter, synthesize)
            # Pass hours parameter to ensure synthesis time window matches report window
            # Invert no_verify flag to get verify_trust boolean
            pipeline_result = await run_pipeline(
                prioritize_hours=hours,
                topic_filters=topic_filters,
                verify_trust=not no_verify
            )

            # Step 2: Generate report from synthesis
            from ..newsletter.newsletter_system import NewsletterSystem
            system = NewsletterSystem()

            # Extract synthesis_id from pipeline to prevent duplicate synthesis generation
            synthesis_id = pipeline_result.get('stages', {}).get('synthesis', {}).get('synthesis_id')

            report_result = await system.generate_report(
                hours=hours,
                send_email=email,
                topic_filters=topic_filters,
                synthesis_id=synthesis_id
            )

            return {
                'pipeline': pipeline_result,
                'report': report_result
            }

        with loading(loading_msg, debug=debug), output_mgr.suppress_output():
            result = asyncio.run(run_brief())

        # Display results
        if result:
            pipeline_summary = result.get("pipeline", {}).get("summary", {})
            report_result = result.get("report", {})

            # Check if filters resulted in 0 articles
            articles_analyzed = report_result.get('articles_analyzed', 0)
            articles_fetched = pipeline_summary.get('articles_fetched', 0)

            if topic_filters and articles_analyzed == 0 and articles_fetched > 0:
                # Filters were too restrictive
                click.echo("\n" + "!" * 80)
                click.echo("NO ARTICLES MATCHED YOUR FILTERS")
                click.echo("!" * 80)
                click.echo(f"\nFetched {articles_fetched} articles, but none matched:")
                if 'topics' in topic_filters:
                    click.echo(f"  Topics: {', '.join(topic_filters['topics'])}")
                if 'scopes' in topic_filters:
                    click.echo(f"  Scopes: {', '.join(topic_filters['scopes'])}")
                click.echo("\nSuggestions:")
                click.echo("  • Try expanding the time window: --hours 48 or --hours 168")
                click.echo("  • Use fewer filters (remove -s or -cs)")
                click.echo("  • Try different filter combinations")
                click.echo("  • Run without filters to see all available content")
                click.echo("=" * 80)
            elif report_result.get("success") and articles_analyzed > 0:
                # Check trust verification status (verification already happened during synthesis)
                trust_verification = report_result.get('trust_verification', {})
                trust_passed = trust_verification.get('passed', True)  # Default to True for old syntheses

                # If --no-verify flag is set, skip trust check and display anyway
                if no_verify or trust_passed:
                    # Display formatted report
                    formatter = BriefFormatter()
                    formatted_report = formatter.format_report(report_result)
                    click.echo(formatted_report)

                    # Show trust verification summary if available (but don't re-verify)
                    if trust_verification and not no_verify:
                        attempts = trust_verification.get('attempts', 1)
                        if trust_passed:
                            click.echo("\n" + "=" * 80)
                            click.echo("TRUST VERIFICATION")
                            click.echo("=" * 80)
                            click.echo(f"✓ Synthesis verified trustworthy (attempts: {attempts})")
                            click.echo("  • Factual accuracy: PASS")
                            click.echo("  • Neutral framing: PASS")
                            click.echo("  • Professional tone: PASS")
                            click.echo("=" * 80)
                else:
                    # Trust verification failed - show failure report instead of brief
                    click.echo("\n" + "!" * 80)
                    click.echo("BRIEF GENERATION FAILED: TRUST VERIFICATION")
                    click.echo("!" * 80)
                    click.echo()
                    click.echo("The AI-generated synthesis did not meet trust standards after 3 attempts.")
                    click.echo()

                    # Show what failed
                    verification_history = trust_verification.get('verification_history', [])
                    if verification_history:
                        final_analysis = verification_history[-1].get('analysis', {})

                        click.echo("VERIFICATION FAILURES:")
                        click.echo("-" * 80)

                        # Fact verification
                        facts = final_analysis.get('facts', {})
                        contradicted = facts.get('contradicted_count', 0)
                        total_claims = facts.get('total_claims', 0)
                        if total_claims > 0:
                            contradicted_ratio = contradicted / total_claims
                            status = "FAIL" if contradicted_ratio > 0.05 else "PASS"
                            click.echo(f"• Factual Accuracy: {status}")
                            click.echo(f"  - Contradicted claims: {contradicted}/{total_claims} ({contradicted_ratio:.1%})")
                            click.echo("  - Threshold: Max 5%")
                            if contradicted > 0:
                                contradicted_claims = facts.get('contradicted', [])
                                for claim in contradicted_claims[:3]:  # Show first 3
                                    click.echo(f"    → {claim.get('claim', 'N/A')[:80]}...")

                        # Bias check
                        bias = final_analysis.get('bias', {})
                        loaded_language = bias.get('loaded_language', [])
                        status = "FAIL" if len(loaded_language) > 3 else "PASS"
                        click.echo(f"\n• Neutral Framing: {status}")
                        click.echo(f"  - Loaded language instances: {len(loaded_language)}")
                        click.echo("  - Threshold: Max 3")
                        if loaded_language:
                            for item in loaded_language[:3]:  # Show first 3
                                click.echo(f"    → \"{item.get('term', 'N/A')}\" - {item.get('issue', 'N/A')[:60]}")

                        # Intimacy/tone check
                        intimacy = final_analysis.get('intimacy', {})
                        high_issues = [i for i in intimacy.get('issues', []) if i.get('severity') == 'HIGH']
                        status = "FAIL" if len(high_issues) > 0 else "PASS"
                        click.echo(f"\n• Professional Tone: {status}")
                        click.echo(f"  - High-severity intimacy issues: {len(high_issues)}")
                        click.echo("  - Threshold: 0 allowed")
                        if high_issues:
                            for issue in high_issues[:3]:  # Show first 3
                                click.echo(f"    → {issue.get('issue_type', 'N/A')}: {issue.get('explanation', 'N/A')[:60]}")

                    click.echo()
                    click.echo("NEXT STEPS:")
                    click.echo("  • The system attempted 3 times with progressively stricter prompts")
                    click.echo("  • No brief was generated to prevent showing unverified information")
                    click.echo("  • Try running again - may succeed on next attempt")
                    click.echo("  • Or use --no-verify to generate brief without verification")
                    click.echo("!" * 80)

            # Display summary footer
            click.echo("\n" + "=" * 80)
            click.echo("PIPELINE SUMMARY")
            click.echo("=" * 80)
            if topic_filters:
                click.echo(f"Filters: {topic_filters}")
            click.echo(f"Articles fetched: {articles_fetched}")
            click.echo(f"Articles analyzed: {articles_analyzed}")

            if report_result.get("success"):
                if report_result.get("local_saved"):
                    click.echo(f"Saved to: {report_result.get('local_path', 'unknown')}")
                if report_result.get("email_sent"):
                    click.echo("Email sent successfully")

            click.echo(f"Duration: {pipeline_summary.get('duration_seconds', 0):.1f}s")
            click.echo("=" * 80)

            # Print profiling report in debug mode
            if debug:
                from ..utils.profiler import get_profiler
                profiler = get_profiler()
                profiler.print_summary()


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
        click.echo(f"\n✓ Fetched {result['total_articles']} articles from {result['successful_feeds']}/{result['total_feeds']} feeds")


@brief_group.command(name="collect")
@click.option('--force', is_flag=True, help='Force all collectors to run even if not due')
@click.option('--name', type=str, help='Run specific collector by name')
def collect_cmd(force, name):
    """Run API data collectors (government calendars, events, jobs)"""
    debug = is_debug_mode()
    output_mgr = get_output_manager()

    message = f"Running collector: {name}" if name else "Running data collectors"
    with loading(message, debug=debug), output_mgr.suppress_output():
        result = asyncio.run(run_collectors(force=force, collector_name=name))

    if result and not debug:
        if name:
            click.echo(f"\n✓ Collector '{name}' completed")
            click.echo(f"  • New items: {result.get('new_items', 0)}")
        else:
            click.echo("\n✓ Data collection completed")
            click.echo(f"  • Collectors run: {result.get('collectors_run', 0)}")
            click.echo(f"  • Total items collected: {result.get('total_items_collected', 0)}")


@brief_group.command(name="collector-status")
def collector_status_cmd():
    """Show status of all data collectors"""
    show_collector_status()


@brief_group.command(name="prioritize")
def prioritize_cmd():
    """Only run prioritization on existing articles"""
    if not settings.anthropic_api_key:
        print("⚠️  Warning: ANTHROPIC_API_KEY not configured")
        print("Analysis requires Claude API access")
        raise click.Abort()

    debug = is_debug_mode()
    with loading("Running prioritization", debug=debug):
        asyncio.run(run_analysis_only())


@brief_group.command(name="trends")
def trends_cmd():
    """Only run trend analysis on existing articles"""
    if not settings.anthropic_api_key:
        print("⚠️  Warning: ANTHROPIC_API_KEY not configured")
        print("Analysis requires Claude API access")
        raise click.Abort()

    debug = is_debug_mode()
    with loading("Running trend analysis", debug=debug):
        asyncio.run(run_analysis_only())


@brief_group.command(name="test-newsletter")
def test_newsletter_cmd():
    """Test reporting system configuration"""
    debug = is_debug_mode()
    with loading("Testing newsletter system", debug=debug):
        asyncio.run(test_newsletter())


@brief_group.command(name="query")
@click.option('--min', 'min_score', type=float, default=0.5, help='Minimum priority score (default: 0.5)')
@click.option('--limit', type=int, default=10, help='Maximum articles to display (default: 10)')
def query_cmd(min_score, limit):
    """Query and display prioritized articles"""
    query_priorities(min_score=min_score, limit=limit)


@brief_group.command(name="cleanup")
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
def cleanup_cmd(dry_run):
    """Clean up old data based on retention policies"""
    from ..maintenance.data_retention import cleanup_old_data

    print("\n" + "=" * 70)
    if dry_run:
        print("DATA RETENTION CLEANUP (DRY RUN)")
    else:
        print("DATA RETENTION CLEANUP")
    print("=" * 70)

    results = cleanup_old_data(dry_run=dry_run)

    print("\n📅 Retention Policies:")
    print(f"  • Articles: {settings.retention_articles_days} days")
    print(f"  • Syntheses: {settings.retention_syntheses_days} days")

    print("\n🗑️  Cleanup Results:")
    articles_deleted = results['articles'].get('deleted', 0)
    syntheses_deleted = results['syntheses'].get('deleted', 0)

    if articles_deleted > 0:
        cutoff = results['articles'].get('cutoff_date', 'N/A')
        print(f"  • Articles: {articles_deleted} {'would be' if dry_run else ''} deleted (older than {cutoff[:10]})")
    else:
        print("  • Articles: No articles to delete")

    if syntheses_deleted > 0:
        cutoff = results['syntheses'].get('cutoff_date', 'N/A')
        print(f"  • Syntheses: {syntheses_deleted} {'would be' if dry_run else ''} deleted (older than {cutoff[:10]})")
    else:
        print("  • Syntheses: No syntheses to delete")

    if dry_run:
        print(f"\n💾 Estimated space to be freed: ~{results['total_freed_mb']} MB")
        print("\n⚠️  This was a DRY RUN - no data was actually deleted")
        print("   Run without --dry-run to perform actual cleanup")
    else:
        print(f"\n💾 Space freed: ~{results['total_freed_mb']} MB")
        print("\n✅ Cleanup complete!")

    print("\n" + "=" * 70)


@brief_group.command(name="retention-status")
def retention_status_cmd():
    """Show current data retention status and policy settings"""
    from ..maintenance.data_retention import get_retention_status

    status = get_retention_status()
    print("\n" + "=" * 70)
    print("DATA RETENTION STATUS")
    print("=" * 70)
    print("\n📋 Retention Policies:")
    print(f"  • Articles: {status['retention_policies']['articles_days']} days")
    print(f"  • Syntheses: {status['retention_policies']['syntheses_days']} days")
    print("  • Semantic Facts: Type-based (60-365 days)")

    print("\n📊 Current Data:")
    articles = status['current_data']['articles']
    print(f"\n  Articles ({articles['total']} total):")
    if articles['oldest']:
        print(f"    • Oldest: {articles['oldest']}")
    if articles['newest']:
        print(f"    • Newest: {articles['newest']}")
    if articles['pending_deletion'] > 0:
        print(f"    • ⚠️  Pending deletion: {articles['pending_deletion']}")
    else:
        print("    • ✓ No articles pending deletion")

    syntheses = status['current_data']['syntheses']
    print(f"\n  Syntheses ({syntheses['total']} total):")
    if syntheses['oldest']:
        print(f"    • Oldest: {syntheses['oldest']}")
    if syntheses['newest']:
        print(f"    • Newest: {syntheses['newest']}")
    if syntheses['pending_deletion'] > 0:
        print(f"    • ⚠️  Pending deletion: {syntheses['pending_deletion']}")
    else:
        print("    • ✓ No syntheses pending deletion")

    print("\n" + "=" * 70)


@brief_group.command(name="health")
def health_cmd():
    """Show system health status and metrics"""
    from ..monitoring.health_monitor import get_system_health

    health = get_system_health()

    print("\n" + "=" * 70)
    print("SYSTEM HEALTH STATUS")
    print("=" * 70)

    # Overall status
    status_emoji = {
        "healthy": "✅",
        "warning": "⚠️ ",
        "degraded": "⚠️ ",
        "error": "❌"
    }.get(health["overall_status"], "❓")

    print(f"\nOverall Status: {status_emoji} {health['overall_status'].upper()}")
    print(f"Checked at: {health['timestamp']}")

    # Database
    db = health["metrics"]["database"]
    print("\n📊 Database:")
    print(f"  • Size: {db['size_mb']} MB")
    print(f"  • Articles: {db['total_articles']:,}")
    print(f"  • Syntheses: {db['total_syntheses']}")
    print(f"  • Memory Facts: {db['total_facts']}")

    # Feeds
    feeds = health["metrics"]["feeds"]
    feed_emoji = "✅" if feeds["status"] == "healthy" else "⚠️ "
    print(f"\n📡 RSS Feeds: {feed_emoji} {feeds['status']}")
    print(f"  • Active: {feeds['active_feeds']}/{feeds['total_feeds']}")
    print(f"  • With errors: {feeds['feeds_with_errors']}")
    print(f"  • Stale (>48h): {feeds['stale_feeds']}")
    if feeds["issues"]:
        for issue in feeds["issues"]:
            print(f"    ⚠️  {issue}")

    # Synthesis
    synth = health["metrics"]["synthesis"]
    synth_emoji = "✅" if synth["status"] == "healthy" else "⚠️ "
    print(f"\n🧠 Synthesis Generation: {synth_emoji} {synth['status']}")
    print(f"  • Recent (7d): {synth['recent_syntheses_7d']}")
    if synth['latest_synthesis']:
        print(f"  • Latest: {synth['latest_synthesis']}")
        print(f"  • Hours since last: {synth['hours_since_last']}")
    if synth["issues"]:
        for issue in synth["issues"]:
            print(f"    ⚠️  {issue}")

    # Memory
    memory = health["metrics"]["memory"]
    print("\n💾 Semantic Memory:")
    print(f"  • Total facts: {memory['total_facts']}")
    print(f"  • Active: {memory['active_facts']}")
    print(f"  • Expired: {memory['expired_facts']}")
    if memory['facts_by_type']:
        print(f"  • By type: {dict(memory['facts_by_type'])}")

    # Retention
    retention = health["metrics"]["retention"]
    ret_emoji = "✅" if retention["status"] == "healthy" else "⚠️ "
    print(f"\n🗑️  Data Retention: {ret_emoji} {retention['status']}")
    print(f"  • Policies: {retention['retention_days_articles']}d articles, {retention['retention_days_syntheses']}d syntheses")
    print(f"  • Pending deletion: {retention['articles_pending_deletion']} articles, {retention['syntheses_pending_deletion']} syntheses")
    if retention["issues"]:
        for issue in retention["issues"]:
            print(f"    ⚠️  {issue}")

    # Disk
    disk = health["metrics"]["disk"]
    disk_emoji = "✅" if disk["status"] == "healthy" else "⚠️ "
    print(f"\n💽 Disk Space: {disk_emoji} {disk['status']}")
    print(f"  • Data directory: {disk['data_dir_size_mb']} MB")

    # Issues summary
    if health["issues"]:
        print(f"\n⚠️  Issues Found ({len(health['issues'])}):")
        for issue in health["issues"]:
            print(f"  • {issue}")

    print("\n" + "=" * 70)


@brief_group.command(name="metrics")
@click.option('--days', type=int, default=7, help='Number of days for metrics (default: 7)')
def metrics_cmd(days):
    """Show performance metrics"""
    from ..monitoring.health_monitor import get_performance_metrics

    metrics = get_performance_metrics(days=days)

    print("\n" + "=" * 70)
    print(f"PERFORMANCE METRICS (Last {days} days)")
    print("=" * 70)
    print(f"\nPeriod: {metrics['start_date']} to {metrics['end_date']}")

    print("\n📰 Article Collection:")
    print(f"  • Total collected: {metrics.get('articles_collected', 0):,}")
    print(f"  • Per day: {metrics.get('articles_per_day', 0)}")

    print("\n🧠 Synthesis Generation:")
    print(f"  • Total syntheses: {metrics.get('syntheses_generated', 0)}")

    print("\n💾 Semantic Memory:")
    print(f"  • Facts created: {metrics.get('facts_created', 0)}")

    print("\n" + "=" * 70)
