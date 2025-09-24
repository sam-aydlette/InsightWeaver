#!/usr/bin/env python3
"""
Run the complete InsightWeaver pipeline
Fetches RSS feeds, deduplicates, and prioritizes articles
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pipeline.orchestrator import run_pipeline
from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Run the complete data pipeline"""
    print("\n" + "=" * 60)
    print("InsightWeaver Data Pipeline")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        # Configuration
        print("Pipeline Configuration:")
        print(f"  • Max concurrent feeds: 10")
        print(f"  • Rate limit: 2 requests/second")
        print(f"  • Deduplication window: 24 hours")
        print(f"  • Prioritization window: 48 hours")
        print(f"  • API Key configured: {'Yes' if settings.anthropic_api_key else 'No'}")
        print()

        print("Starting pipeline...")
        print("-" * 40)

        # Run pipeline
        results = await run_pipeline(
            max_concurrent=10,
            rate_limit=2.0,
            dedup_hours=24,
            prioritize_hours=48,
            prioritize_limit=None  # Process all articles
        )

        # Display results
        print("\n" + "=" * 60)
        print("PIPELINE RESULTS")
        print("=" * 60)

        # Stage 1: RSS Fetching
        fetch = results["stages"].get("fetch", {})
        if not fetch.get("skipped"):
            print("\n📡 RSS Feed Fetching:")
            print(f"   • Feeds processed: {fetch.get('total_feeds', 0)}")
            print(f"   • Successful feeds: {fetch.get('successful_feeds', 0)}")
            print(f"   • Failed feeds: {fetch.get('failed_feeds', 0)}")
            print(f"   • Articles retrieved: {fetch.get('total_articles', 0)}")
            print(f"   • Time taken: {fetch.get('total_time', 0):.1f}s")

        # Stage 2: Deduplication
        dedup = results["stages"].get("deduplication", {})
        if not dedup.get("skipped"):
            print("\n🔍 Deduplication:")
            print(f"   • Articles processed: {dedup.get('processed_articles', 0)}")
            print(f"   • Exact duplicates: {dedup.get('exact_duplicates', 0)}")
            print(f"   • Near duplicates: {dedup.get('near_duplicates', 0)}")
            print(f"   • Total removed: {dedup.get('total_duplicates', 0)}")

        # Stage 3: Prioritization
        priority = results["stages"].get("prioritization", {})
        if not priority.get("skipped"):
            print("\n🎯 Prioritization:")
            print(f"   • Articles analyzed: {priority.get('articles_processed', 0)}")
            summary = priority.get("summary", {})
            print(f"   • High priority (≥0.7): {summary.get('high_priority_articles', 0)}")
            print(f"   • Updated in database: {summary.get('updated_articles', 0)}")
        elif priority.get("skipped"):
            print(f"\n⚠️  Prioritization: Skipped ({priority.get('reason', 'Unknown reason')})")

        # Summary
        summary = results.get("summary", {})
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✅ Pipeline completed successfully")
        print(f"⏱️  Duration: {summary.get('duration_seconds', 0):.1f} seconds")
        print(f"📊 Total articles fetched: {summary.get('articles_fetched', 0)}")
        print(f"🗑️  Duplicates removed: {summary.get('duplicates_removed', 0)}")
        print(f"🔥 High priority articles: {summary.get('high_priority_articles', 0)}")

        # Display top priorities if available
        if summary.get('high_priority_articles', 0) > 0:
            print("\n📌 Top Priority Articles:")
            from src.agents.prioritization_agent import PrioritizationAgent
            agent = PrioritizationAgent()
            top_articles = agent.get_high_priority_articles(min_score=0.8, limit=3)

            for i, article in enumerate(top_articles, 1):
                print(f"\n   {i}. [{article.priority_score:.2f}] {article.title[:80]}...")
                if article.priority_metadata and 'reasoning' in article.priority_metadata:
                    print(f"      → {article.priority_metadata['reasoning'][:100]}...")

        print("\n" + "=" * 60)
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        logging.exception("Pipeline execution failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())