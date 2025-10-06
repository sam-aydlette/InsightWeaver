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

    results = await run_pipeline(
        max_concurrent=10,
        rate_limit=2.0,
        dedup_hours=24,
        prioritize_hours=48,
        prioritize_limit=None  # Two-stage analysis processes all articles efficiently
    )

    # Analysis integrated into pipeline orchestrator
    if not settings.anthropic_api_key:
        print("\n⚠️ Skipping analysis - no API key configured")

    # Display summary
    summary = results.get("summary", {})
    print("\n" + "=" * 60)
    print("Analysis Pipeline Complete")
    print(f"• Articles fetched: {summary.get('articles_fetched', 0)}")
    print(f"• Duplicates removed: {summary.get('duplicates_removed', 0)}")
    print(f"• Articles analyzed: {summary.get('articles_synthesized', 0)}")
    print(f"• Narrative generated: {summary.get('narrative_generated', False)}")
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

    args = parser.parse_args()

    try:
        # Handle different modes
        if args.setup:
            setup_database()

        elif args.query:
            query_priorities(min_score=args.min, limit=args.limit)

        elif args.fetch:
            asyncio.run(run_fetch_only())

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