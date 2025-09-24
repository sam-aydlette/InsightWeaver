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
from src.agents.prioritization_agent import PrioritizationAgent
from src.agents.trend_agent import TrendAnalysisAgent
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


async def run_prioritize_only():
    """Run only prioritization on existing articles"""
    print("Running article prioritization...")
    agent = PrioritizationAgent()
    results = await agent.run_analysis(hours=48)
    summary = results.get("summary", {})
    print(f"Prioritized {results['articles_processed']} articles")
    print(f"High priority articles: {summary.get('high_priority_articles', 0)}")
    return results


async def run_trend_analysis():
    """Run trend analysis on existing articles"""
    print("Running trend analysis...")
    agent = TrendAnalysisAgent()
    results = await agent.run_analysis(days=30)  # Analyze last 30 days
    summary = results.get("summary", {})
    print(f"Analyzed {results['articles_processed']} articles")
    print(f"Trends detected: {summary.get('trends_detected', 0)}")

    # Display key trend findings
    trend_analysis = results.get("trend_analysis", [])
    if trend_analysis:
        print("\nKey Trend Movements:")
        for trend in sorted(trend_analysis, key=lambda x: x.get('confidence', 0), reverse=True)[:5]:
            trend_name = trend.get('trend', '').replace('_', ' ').title()
            direction = trend.get('direction', 'NEUTRAL')
            confidence = trend.get('confidence', 0)
            print(f"  • {trend_name}: {direction} (confidence: {confidence:.2f})")

    return results


async def run_full_pipeline():
    """Run complete pipeline: fetch -> deduplicate -> prioritize"""
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

    # Display summary
    summary = results.get("summary", {})
    print("\n" + "=" * 60)
    print("Pipeline Complete")
    print(f"• Articles fetched: {summary.get('articles_fetched', 0)}")
    print(f"• Duplicates removed: {summary.get('duplicates_removed', 0)}")
    print(f"• High priority articles: {summary.get('high_priority_articles', 0)}")
    print(f"• Duration: {summary.get('duration_seconds', 0):.1f}s")
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
    print(f"✓ Loaded {stats['active_feeds']} active feeds across {len(stats['categories'])} categories")


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
  python main.py                    # Run full pipeline (default)
  python main.py --fetch             # Only fetch RSS feeds
  python main.py --prioritize        # Only run prioritization
  python main.py --trends            # Only run trend analysis
  python main.py --setup             # Initialize database and feeds
  python main.py --query             # Query priority articles
  python main.py --query --min 0.7  # Query high priority only
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

        elif args.prioritize:
            if not settings.anthropic_api_key:
                print("⚠️  Warning: ANTHROPIC_API_KEY not configured")
                print("Prioritization requires Claude API access")
                sys.exit(1)
            asyncio.run(run_prioritize_only())

        elif args.trends:
            if not settings.anthropic_api_key:
                print("⚠️  Warning: ANTHROPIC_API_KEY not configured")
                print("Trend analysis requires Claude API access")
                sys.exit(1)
            asyncio.run(run_trend_analysis())

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