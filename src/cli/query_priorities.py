#!/usr/bin/env python3
"""
Query and display prioritized articles from the database
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.models import Article, RSSFeed
from src.database.connection import get_db

def query_prioritized_articles(
    min_score: float = 0.0,
    hours: int = 48,
    limit: int = 20,
    show_all_scores: bool = False
):
    """
    Query prioritized articles from the database

    Args:
        min_score: Minimum priority score (0.0-1.0)
        hours: Look back this many hours
        limit: Maximum number of articles to return
        show_all_scores: Show breakdown of all scoring components
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_db() as db:
        # Query articles with priority scores
        query = db.query(Article).join(RSSFeed).filter(
            Article.fetched_at >= cutoff_time,
            Article.priority_score.isnot(None),
            Article.priority_score >= min_score
        ).order_by(desc(Article.priority_score)).limit(limit)

        articles = query.all()

        if not articles:
            print(f"No prioritized articles found with score >= {min_score} in last {hours} hours")
            return

        print(f"\n📊 PRIORITIZED ARTICLES (Score >= {min_score})")
        print("=" * 80)
        print(f"Found {len(articles)} articles | Time window: {hours}h | Sorted by priority ↓")
        print("=" * 80)

        for i, article in enumerate(articles, 1):
            # Basic info
            print(f"\n{i}. [{article.priority_score:.2f}] {article.title[:100]}")
            print(f"   📰 Source: {article.feed.name}")
            print(f"   🔗 URL: {article.url}")
            print(f"   📅 Published: {article.published_date}")

            # Priority metadata if available
            if article.priority_metadata:
                meta = article.priority_metadata

                # Show reasoning
                if 'reasoning' in meta:
                    print(f"   💭 Reasoning: {meta['reasoning'][:150]}...")

                # Show detailed scores if requested
                if show_all_scores:
                    if 'timeliness_score' in meta:
                        print(f"   ⏰ Timeliness: {meta['timeliness_score']:.2f}")
                    if 'impact_score' in meta:
                        print(f"   💥 Impact: {meta['impact_score']:.2f}")
                    if 'actionability_score' in meta:
                        print(f"   🎯 Actionability: {meta['actionability_score']:.2f}")

                # Show key factors
                if 'key_factors' in meta and meta['key_factors']:
                    print(f"   🏷️  Tags: {', '.join(meta['key_factors'])}")

                # Show when prioritized
                if 'prioritization_timestamp' in meta:
                    print(f"   🤖 Analyzed: {meta['prioritization_timestamp']}")

        # Summary statistics
        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)

        scores = [a.priority_score for a in articles]
        high_priority = len([a for a in articles if a.priority_score >= 0.7])
        medium_priority = len([a for a in articles if 0.4 <= a.priority_score < 0.7])
        low_priority = len([a for a in articles if a.priority_score < 0.4])

        print(f"📈 Score Distribution:")
        print(f"   High (≥0.7): {high_priority} articles")
        print(f"   Medium (0.4-0.7): {medium_priority} articles")
        print(f"   Low (<0.4): {low_priority} articles")
        print(f"   Average Score: {sum(scores)/len(scores):.2f}")
        print(f"   Highest Score: {max(scores):.2f}")
        print(f"   Lowest Score: {min(scores):.2f}")

def main():
    """Interactive query interface"""
    print("InsightWeaver Priority Query Tool")
    print("=" * 40)

    # Get parameters from user
    try:
        print("\nQuery Parameters (press Enter for defaults):")

        min_score_input = input("Minimum priority score [0.0-1.0] (default 0.5): ").strip()
        min_score = float(min_score_input) if min_score_input else 0.5

        hours_input = input("Hours to look back (default 48): ").strip()
        hours = int(hours_input) if hours_input else 48

        limit_input = input("Maximum articles to show (default 20): ").strip()
        limit = int(limit_input) if limit_input else 20

        show_all_input = input("Show detailed scores? [y/N]: ").strip().lower()
        show_all = show_all_input == 'y'

        # Run query
        query_prioritized_articles(
            min_score=min_score,
            hours=hours,
            limit=limit,
            show_all_scores=show_all
        )

    except ValueError as e:
        print(f"❌ Invalid input: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nQuery cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()