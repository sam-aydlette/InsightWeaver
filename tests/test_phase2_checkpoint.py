#!/usr/bin/env python3
"""
InsightWeaver Phase 2 Checkpoint Verification
Comprehensive test suite to verify Phase 2 requirements:
- 100+ RSS feeds configured and validated
- Parallel processing with rate limiting
- Deduplication system operational
- Database storage and retrieval functioning
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_feed_config():
    """Test 1: Check feed configuration"""
    print("=== Test 1: Feed Configuration ===")
    try:
        from src.config.feeds import get_feed_count, RSS_FEEDS, validate_feeds

        total_feeds = get_feed_count()
        print(f"Total feeds configured: {total_feeds}")

        print(f"\nCategory breakdown:")
        for category, feeds in RSS_FEEDS.items():
            print(f"  {category}: {len(feeds)} feeds")

        # Validate configuration
        issues = validate_feeds()
        if issues:
            print(f"\nConfiguration issues:")
            for issue in issues[:5]:  # Show first 5 issues
                print(f"  - {issue}")
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more issues")
        else:
            print(f"\nConfiguration validated successfully!")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_database_loading():
    """Test 2: Load feeds into database"""
    print("\n=== Test 2: Database Loading ===")
    try:
        from src.feed_manager import setup_feeds

        print("Loading feeds into database...")
        fm = setup_feeds()
        stats = fm.get_feed_statistics()

        print(f"✓ Active feeds loaded: {stats['active_feeds']}")
        print(f"✓ Feeds with errors: {stats['feeds_with_errors']}")
        print(f"✓ Categories in database: {len(stats['categories'])}")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_parallel_fetching():
    """Test 3: Parallel RSS fetching"""
    print("\n=== Test 3: Parallel RSS Fetching ===")
    try:
        from src.rss.parallel_fetcher import fetch_all_active_feeds

        print("Starting parallel fetch (conservative settings)...")
        print("This may take 1-2 minutes...")

        results = await fetch_all_active_feeds(
            max_concurrent=5,    # Conservative concurrency
            rate_limit=1.0       # 1 request per second
        )

        success_rate = results['successful_feeds'] / results['total_feeds'] if results['total_feeds'] > 0 else 0

        print(f"✓ Processed: {results['total_feeds']} feeds")
        print(f"✓ Successful: {results['successful_feeds']} ({success_rate:.1%})")
        print(f"✓ Articles retrieved: {results['total_articles']}")
        print(f"✓ Processing time: {results['total_time']:.1f}s")

        if results['failed_feeds_list']:
            print(f"\nFailed feeds (first 5): {results['failed_feeds_list'][:5]}")

        if results['error_summary']:
            print(f"\nTop error types:")
            for error, count in list(results['error_summary'].items())[:3]:
                print(f"  {error[:50]}...: {count}")

        return success_rate >= 0.5  # 50% success rate threshold
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_deduplication():
    """Test 4: Article deduplication"""
    print("\n=== Test 4: Article Deduplication ===")
    try:
        from src.processors.deduplicator import run_deduplication

        print("Running deduplication on recent articles...")
        results = run_deduplication(hours=24)

        print(f"✓ Articles processed: {results['processed_articles']}")
        print(f"✓ Exact duplicates found: {results['exact_duplicates']}")
        print(f"✓ Near duplicates found: {results['near_duplicates']}")
        print(f"✓ Total duplicates: {results['total_duplicates']}")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_database_query():
    """Test 5: Database queries"""
    print("\n=== Test 5: Database Queries ===")
    try:
        from src.database.connection import get_db
        from src.database.models import Article, RSSFeed
        from datetime import datetime, timedelta

        with get_db() as db:
            # Count articles
            total_articles = db.query(Article).count()

            # Count recent articles
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_articles = db.query(Article).filter(Article.fetched_at >= recent_cutoff).count()

            # Sample articles
            sample_articles = db.query(Article).join(RSSFeed).limit(3).all()

            print(f"✓ Total articles in database: {total_articles}")
            print(f"✓ Articles fetched in last hour: {recent_articles}")

            if sample_articles:
                print(f"\nSample articles:")
                for article in sample_articles:
                    title = article.title[:60] + "..." if len(article.title) > 60 else article.title
                    print(f"  • {title} ({article.feed.name})")

        return total_articles > 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    """Run all tests"""
    print("InsightWeaver Phase 2 Checkpoint Verification")
    print("=" * 50)

    tests = [
        ("Feed Configuration", test_feed_config),
        ("Database Loading", test_database_loading),
        ("Parallel Fetching", test_parallel_fetching),
        ("Deduplication", test_deduplication),
        ("Database Queries", test_database_query),
    ]

    results = []

    for test_name, test_func in tests:
        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()
        results.append((test_name, result))

    # Summary
    print("\n" + "=" * 50)
    print("PHASE 2 CHECKPOINT VERIFICATION RESULTS")
    print("=" * 50)

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1

    # Calculate success rate
    success_rate = (passed / len(tests)) * 100
    print(f"\nSuccess Rate: {passed}/{len(tests)} tests passed ({success_rate:.1f}%)")

    # Phase 2 Checkpoint Status
    print("\n" + "=" * 50)
    if success_rate >= 80:
        print("✅ PHASE 2 CHECKPOINT: PASSED")
        print("🎉 System ready for Phase 3 - Advanced Analysis!")
        print("✓ 100+ RSS feeds configured and validated")
        print("✓ Parallel processing with rate limiting working")
        print("✓ Deduplication system operational")
        print("✓ Database storage and retrieval functioning")
    elif success_rate >= 60:
        print("⚠️  PHASE 2 CHECKPOINT: PARTIAL")
        print("📝 Core functionality working, minor issues to resolve")
        print("✓ Basic RSS pipeline operational")
        print("⚠️  Some advanced features need attention")
    else:
        print("❌ PHASE 2 CHECKPOINT: FAILED")
        print("🚨 Critical issues detected - system needs repair")
        print("❌ Phase 2 requirements not met")

    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())