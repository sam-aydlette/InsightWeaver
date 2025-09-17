#!/usr/bin/env python3
"""
CLI tool for running article prioritization
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.prioritization_agent import PrioritizationAgent

async def main():
    """Run prioritization analysis"""
    print("InsightWeaver Article Prioritization")
    print("=" * 40)

    try:
        agent = PrioritizationAgent()

        print("Starting prioritization analysis...")
        print("This will analyze articles from the last 48 hours using Anthropic Claude API...")

        results = await agent.run_analysis(hours=48, limit=100)

        print(f"\n✅ Analysis Complete!")
        print(f"📊 Analysis Run ID: {results['analysis_run_id']}")
        print(f"📰 Articles Processed: {results['articles_processed']}")

        if results['articles_processed'] > 0:
            summary = results.get('summary', {})
            print(f"🔥 High Priority Articles: {summary.get('high_priority_articles', 0)}")

            # Show top priority articles
            top_articles = agent.get_high_priority_articles(min_score=0.7, limit=5)
            if top_articles:
                print(f"\n📋 Top Priority Articles:")
                for i, article in enumerate(top_articles, 1):
                    score = article.priority_score or 0
                    reasoning = ""
                    if article.priority_metadata and 'reasoning' in article.priority_metadata:
                        reasoning = article.priority_metadata['reasoning'][:100] + "..."

                    print(f"  {i}. [{score:.2f}] {article.title[:80]}...")
                    if reasoning:
                        print(f"     → {reasoning}")
                    print()

            # Show summary stats
            stats = agent.get_prioritization_summary(hours=48)
            print(f"📈 Summary Statistics:")
            print(f"   High Priority (≥0.7): {stats.get('high_priority_count', 0)}")
            print(f"   Medium Priority (0.4-0.6): {stats.get('medium_priority_count', 0)}")
            print(f"   Low Priority (<0.4): {stats.get('low_priority_count', 0)}")
            print(f"   Average Score: {stats.get('average_score', 0):.2f}")
        else:
            print("ℹ️  No recent articles found to prioritize")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())