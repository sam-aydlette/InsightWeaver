#!/usr/bin/env python3
"""
InsightWeaver - Main Application Entry Point
Intelligent RSS feed aggregation and analysis system
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path if running directly
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pipeline.orchestrator import run_pipeline
from src.feed_manager import setup_feeds
from src.config.settings import settings
from src.database.connection import create_tables

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_fetch_only():
    """Run only RSS fetching"""
    from src.rss.parallel_fetcher import fetch_all_active_feeds
    print("Running RSS feed fetching...")
    results = await fetch_all_active_feeds()
    print(f"Fetched {results['total_articles']} articles from {results['successful_feeds']}/{results['total_feeds']} feeds")
    return results


async def run_analysis_only():
    """Run analysis on existing articles using context-driven approach"""
    print("Running article analysis...")
    # TODO: Implement context-driven analysis
    print("⚠️ Analysis functionality being refactored to context-engineering approach")
    return {"status": "pending_refactor"}


async def run_collectors(force=False, collector_name=None):
    """Run API data collectors"""
    from src.collectors.manager import CollectorManager

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
    from src.collectors.manager import CollectorManager

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
    from src.newsletter.newsletter_system import NewsletterSystem

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
        prioritize_limit=None  # Two-stage analysis processes all articles efficiently
    )

    # Step 2: Run API data collectors
    print("\n" + "-" * 60)
    print("Running API Data Collectors")
    print("-" * 60 + "\n")

    try:
        from src.collectors.manager import CollectorManager
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

    # Analysis integrated into pipeline orchestrator
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
            from src.newsletter.newsletter_system import NewsletterSystem
            newsletter_system = NewsletterSystem()

            # Generate intelligence report for last 24 hours
            print("📊 Generating Intelligence Report...")
            report_result = await newsletter_system.generate_report(hours=24, send_email=True)

            if report_result["success"]:
                print(f"✅ Report generated successfully")
                print(f"   • Articles analyzed: {report_result['articles_analyzed']}")
                print(f"   • Report type: {report_result['report_type']}")
                if report_result.get("local_saved"):
                    print(f"   • Saved to: {report_result['local_path']}")
                if report_result.get("email_sent"):
                    print(f"   • Email sent successfully")

            # Update results with report data
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
    from src.database.models import Article
    from src.database.connection import get_db

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


def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description="InsightWeaver - Intelligent RSS Feed Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              # Run full pipeline
  python main.py --report                     # Generate report (last 24h)
  python main.py --report --hours 48          # Last 48 hours
  python main.py --report --hours 168         # Last week (168h)
  python main.py --report --start-date 2025-10-01 --end-date 2025-10-07
  python main.py --fetch                      # Only fetch RSS feeds
  python main.py --collect                    # Run API data collectors
  python main.py --collect --force            # Force all collectors to run
  python main.py --collect --name usajobs     # Run specific collector
  python main.py --collector-status           # Show collector status
  python main.py --retention-status           # Show data retention status
  python main.py --cleanup --dry-run          # Preview cleanup (safe)
  python main.py --cleanup                    # Clean up old data
  python main.py --health                     # Show system health status
  python main.py --metrics                    # Show performance metrics (7d)
  python main.py --metrics --days 30          # Show 30-day metrics
  python main.py --test-newsletter            # Test reporting system
  python main.py --setup                      # Initialize database and feeds
  python main.py --query                      # Query priority articles
        """
    )

    parser.add_argument(
        "--setup",
        action="store_true",
        help="Setup database and load RSS feeds"
    )

    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Only fetch RSS feeds (no analysis)"
    )

    parser.add_argument(
        "--collect",
        action="store_true",
        help="Run API data collectors (government calendars, events, jobs)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force collectors to run even if not due (use with --collect)"
    )

    parser.add_argument(
        "--name",
        type=str,
        help="Run specific collector by name (use with --collect)"
    )

    parser.add_argument(
        "--collector-status",
        action="store_true",
        help="Show status of all data collectors"
    )

    parser.add_argument(
        "--prioritize",
        action="store_true",
        help="Only run prioritization on existing articles"
    )

    parser.add_argument(
        "--trends",
        action="store_true",
        help="Only run trend analysis on existing articles"
    )

    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate intelligence report (flexible time window)"
    )

    parser.add_argument(
        "--hours",
        type=int,
        help="Look back N hours for report (default: 24)"
    )

    parser.add_argument(
        "--start-date",
        type=str,
        help="Report start date (YYYY-MM-DD or YYYY-MM-DD HH:MM)"
    )

    parser.add_argument(
        "--end-date",
        type=str,
        help="Report end date (YYYY-MM-DD or YYYY-MM-DD HH:MM)"
    )

    parser.add_argument(
        "--test-newsletter",
        action="store_true",
        help="Test reporting system configuration"
    )

    parser.add_argument(
        "--query",
        action="store_true",
        help="Query and display prioritized articles"
    )

    parser.add_argument(
        "--min",
        type=float,
        default=0.5,
        help="Minimum priority score for query (default: 0.5)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum articles to display in query (default: 10)"
    )

    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up old data based on retention policies"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting (use with --cleanup)"
    )

    parser.add_argument(
        "--retention-status",
        action="store_true",
        help="Show current data retention status and policy settings"
    )

    parser.add_argument(
        "--health",
        action="store_true",
        help="Show system health status and metrics"
    )

    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Show performance metrics"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days for metrics (default: 7)"
    )

    args = parser.parse_args()

    try:
        # Handle different modes
        if args.setup:
            setup_database()

        elif args.collector_status:
            show_collector_status()

        elif args.query:
            query_priorities(min_score=args.min, limit=args.limit)

        elif args.retention_status:
            from src.maintenance.data_retention import get_retention_status
            import json
            status = get_retention_status()
            print("\n" + "=" * 70)
            print("DATA RETENTION STATUS")
            print("=" * 70)
            print("\n📋 Retention Policies:")
            print(f"  • Articles: {status['retention_policies']['articles_days']} days")
            print(f"  • Syntheses: {status['retention_policies']['syntheses_days']} days")
            print(f"  • Semantic Facts: Type-based (60-365 days)")

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
                print(f"    • ✓ No articles pending deletion")

            syntheses = status['current_data']['syntheses']
            print(f"\n  Syntheses ({syntheses['total']} total):")
            if syntheses['oldest']:
                print(f"    • Oldest: {syntheses['oldest']}")
            if syntheses['newest']:
                print(f"    • Newest: {syntheses['newest']}")
            if syntheses['pending_deletion'] > 0:
                print(f"    • ⚠️  Pending deletion: {syntheses['pending_deletion']}")
            else:
                print(f"    • ✓ No syntheses pending deletion")

            print("\n" + "=" * 70)

        elif args.health:
            from src.monitoring.health_monitor import get_system_health
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
            print(f"\n📊 Database:")
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
            print(f"\n💾 Semantic Memory:")
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

        elif args.metrics:
            from src.monitoring.health_monitor import get_performance_metrics
            metrics = get_performance_metrics(days=args.days)

            print("\n" + "=" * 70)
            print(f"PERFORMANCE METRICS (Last {args.days} days)")
            print("=" * 70)
            print(f"\nPeriod: {metrics['start_date']} to {metrics['end_date']}")

            print(f"\n📰 Article Collection:")
            print(f"  • Total collected: {metrics.get('articles_collected', 0):,}")
            print(f"  • Per day: {metrics.get('articles_per_day', 0)}")

            print(f"\n🧠 Synthesis Generation:")
            print(f"  • Total syntheses: {metrics.get('syntheses_generated', 0)}")

            print(f"\n💾 Semantic Memory:")
            print(f"  • Facts created: {metrics.get('facts_created', 0)}")

            print("\n" + "=" * 70)

        elif args.cleanup:
            from src.maintenance.data_retention import cleanup_old_data
            print("\n" + "=" * 70)
            if args.dry_run:
                print("DATA RETENTION CLEANUP (DRY RUN)")
            else:
                print("DATA RETENTION CLEANUP")
            print("=" * 70)

            results = cleanup_old_data(dry_run=args.dry_run)

            print(f"\n📅 Retention Policies:")
            print(f"  • Articles: {settings.retention_articles_days} days")
            print(f"  • Syntheses: {settings.retention_syntheses_days} days")

            print(f"\n🗑️  Cleanup Results:")
            articles_deleted = results['articles'].get('deleted', 0)
            syntheses_deleted = results['syntheses'].get('deleted', 0)

            if articles_deleted > 0:
                cutoff = results['articles'].get('cutoff_date', 'N/A')
                print(f"  • Articles: {articles_deleted} {'would be' if args.dry_run else ''} deleted (older than {cutoff[:10]})")
            else:
                print(f"  • Articles: No articles to delete")

            if syntheses_deleted > 0:
                cutoff = results['syntheses'].get('cutoff_date', 'N/A')
                print(f"  • Syntheses: {syntheses_deleted} {'would be' if args.dry_run else ''} deleted (older than {cutoff[:10]})")
            else:
                print(f"  • Syntheses: No syntheses to delete")

            if args.dry_run:
                print(f"\n💾 Estimated space to be freed: ~{results['total_freed_mb']} MB")
                print("\n⚠️  This was a DRY RUN - no data was actually deleted")
                print("   Run without --dry-run to perform actual cleanup")
            else:
                print(f"\n💾 Space freed: ~{results['total_freed_mb']} MB")
                print("\n✅ Cleanup complete!")

            print("\n" + "=" * 70)

        elif args.fetch:
            asyncio.run(run_fetch_only())

        elif args.collect:
            asyncio.run(run_collectors(force=args.force, collector_name=args.name))

        elif args.prioritize or args.trends:
            if not settings.anthropic_api_key:
                print("⚠️  Warning: ANTHROPIC_API_KEY not configured")
                print("Analysis requires Claude API access")
                sys.exit(1)
            asyncio.run(run_analysis_only())

        elif args.report:
            if not settings.anthropic_api_key:
                print("⚠️  Warning: ANTHROPIC_API_KEY not configured")
                print("Report generation requires Claude API access")
                sys.exit(1)

            # Parse date arguments if provided
            start_date = None
            end_date = None

            if args.start_date:
                try:
                    if len(args.start_date) == 10:  # YYYY-MM-DD
                        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
                    else:  # YYYY-MM-DD HH:MM
                        start_date = datetime.strptime(args.start_date, '%Y-%m-%d %H:%M')
                except ValueError as e:
                    print(f"❌ Invalid start date format: {args.start_date}")
                    print("Use YYYY-MM-DD or 'YYYY-MM-DD HH:MM'")
                    sys.exit(1)

            if args.end_date:
                try:
                    if len(args.end_date) == 10:  # YYYY-MM-DD
                        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
                    else:  # YYYY-MM-DD HH:MM
                        end_date = datetime.strptime(args.end_date, '%Y-%m-%d %H:%M')
                except ValueError as e:
                    print(f"❌ Invalid end date format: {args.end_date}")
                    print("Use YYYY-MM-DD or 'YYYY-MM-DD HH:MM'")
                    sys.exit(1)

            async def run_report():
                from src.newsletter.newsletter_system import NewsletterSystem
                system = NewsletterSystem()
                result = await system.generate_report(
                    start_date=start_date,
                    end_date=end_date,
                    hours=args.hours,
                    send_email=True  # Enable email by default
                )

                if result["success"]:
                    print(f"✅ Report generated successfully")
                    print(f"   • Type: {result['report_type']}")
                    print(f"   • Duration: {result['duration_hours']:.1f}h")
                    print(f"   • Articles analyzed: {result['articles_analyzed']}")
                    if result.get("local_saved"):
                        print(f"   • Saved to: {result['local_path']}")
                    if result.get("email_sent"):
                        print(f"   • Email sent successfully")
                else:
                    print(f"❌ Report generation failed: {result.get('error')}")

            asyncio.run(run_report())

        elif args.test_newsletter:
            asyncio.run(test_newsletter())

        else:
            # Default: run full pipeline
            asyncio.run(run_full_pipeline())

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Application error: {e}")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()