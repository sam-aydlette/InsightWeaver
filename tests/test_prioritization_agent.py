#!/usr/bin/env python3
"""
Test Suite for Prioritization Agent
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_agent_configuration():
    """Test 1: Agent Configuration and Setup"""
    print("=== Test 1: Agent Configuration ===")
    try:
        from src.agents.prioritization_agent import PrioritizationAgent
        from src.config.settings import settings

        agent = PrioritizationAgent()
        print(f"✓ Agent created: {agent.agent_name} v{agent.agent_version}")

        # Check Anthropic API key configuration
        if settings.anthropic_api_key:
            print("✓ Anthropic API key configured")
        else:
            print("⚠️  Anthropic API key not configured (set ANTHROPIC_API_KEY)")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_database_setup():
    """Test 2: Database Schema for Prioritization"""
    print("\n=== Test 2: Database Schema ===")
    try:
        from src.database.models import Article, AnalysisRun
        from src.database.connection import get_db

        with get_db() as db:
            # Check for recent articles
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            recent_articles = db.query(Article).filter(
                Article.fetched_at >= recent_cutoff
            ).count()

            print(f"✓ Recent articles available: {recent_articles}")

            # Check analysis runs table
            analysis_runs = db.query(AnalysisRun).count()
            print(f"✓ Analysis runs table accessible: {analysis_runs} runs")

            # Check priority fields
            sample_article = db.query(Article).first()
            if sample_article:
                has_priority_score = hasattr(sample_article, 'priority_score')
                has_priority_metadata = hasattr(sample_article, 'priority_metadata')
                print(f"✓ Priority score field: {has_priority_score}")
                print(f"✓ Priority metadata field: {has_priority_metadata}")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_prioritization_dry_run():
    """Test 3: Prioritization Dry Run (without Claude API)"""
    print("\n=== Test 3: Prioritization Dry Run ===")
    try:
        from src.agents.prioritization_agent import PrioritizationAgent
        from src.database.models import Article
        from src.database.connection import get_db

        agent = PrioritizationAgent()

        # Get recent articles directly from database to avoid session issues
        with get_db() as db:
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            articles = db.query(Article).filter(
                Article.fetched_at >= recent_cutoff,
                Article.title.isnot(None),
                Article.normalized_content.isnot(None)
            ).limit(5).all()

            print(f"✓ Retrieved {len(articles)} recent articles for testing")

            if articles:
                # Test system prompt generation
                system_prompt = agent._create_system_prompt()
                print(f"✓ System prompt generated: {len(system_prompt)} characters")
                print(f"   Contains 'timeliness': {'timeliness' in system_prompt.lower()}")
                print(f"   Contains 'impact': {'impact' in system_prompt.lower()}")
                print(f"   Contains 'actionability': {'actionability' in system_prompt.lower()}")

                # Test article data preparation (within session context)
                articles_data = []
                for article in articles[:2]:  # Test with 2 articles
                    # Handle timezone-aware comparison
                    fetched_at = article.fetched_at.replace(tzinfo=timezone.utc) if article.fetched_at.tzinfo is None else article.fetched_at
                    article_age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600

                    # Get feed name within session
                    feed_name = article.feed.name if article.feed else "Unknown"

                    articles_data.append({
                        "id": article.id,
                        "title": article.title or "No title",
                        "content": (article.normalized_content or article.description or "")[:2000],
                        "published_date": article.published_date.isoformat() if article.published_date else "Unknown",
                        "source": feed_name,
                        "age_hours": round(article_age_hours, 1),
                        "url": article.url
                    })

                print(f"✓ Prepared {len(articles_data)} articles for analysis")
                for i, article_data in enumerate(articles_data, 1):
                    print(f"   Article {i}: {article_data['title'][:50]}... (Age: {article_data['age_hours']}h)")

            else:
                print("ℹ️  No recent articles available for testing")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_priority_queries():
    """Test 4: Priority Query Functions"""
    print("\n=== Test 4: Priority Query Functions ===")
    try:
        from src.agents.prioritization_agent import PrioritizationAgent

        agent = PrioritizationAgent()

        # Test getting high priority articles
        high_priority = agent.get_high_priority_articles(min_score=0.7, limit=10)
        print(f"✓ High priority articles query: {len(high_priority)} articles")

        # Test prioritization summary
        summary = agent.get_prioritization_summary(hours=48)
        print(f"✓ Summary generated:")
        print(f"   Total articles: {summary.get('total_articles', 0)}")
        print(f"   High priority: {summary.get('high_priority_count', 0)}")
        print(f"   Average score: {summary.get('average_score', 0):.2f}")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_analysis_run_tracking():
    """Test 5: Analysis Run Tracking"""
    print("\n=== Test 5: Analysis Run Tracking ===")
    try:
        from src.agents.prioritization_agent import PrioritizationAgent

        agent = PrioritizationAgent()

        # Test starting an analysis run
        run_id = agent.start_analysis_run("test_prioritization", {"test": True})
        print(f"✓ Started analysis run: {run_id}")

        # Test completing an analysis run
        agent.complete_analysis_run(run_id, 5)
        print(f"✓ Completed analysis run: {run_id}")

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    """Run all tests"""
    print("InsightWeaver Prioritization Agent Test Suite")
    print("=" * 50)

    tests = [
        ("Agent Configuration", test_agent_configuration),
        ("Database Schema", test_database_setup),
        ("Prioritization Dry Run", test_prioritization_dry_run),
        ("Priority Queries", test_priority_queries),
        ("Analysis Run Tracking", test_analysis_run_tracking),
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
    print("PRIORITIZATION AGENT TEST RESULTS")
    print("=" * 50)

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1

    success_rate = (passed / len(tests)) * 100
    print(f"\nSuccess Rate: {passed}/{len(tests)} tests passed ({success_rate:.1f}%)")

    if success_rate >= 80:
        print("✅ PRIORITIZATION AGENT: READY")
        print("🚀 Ready for Claude API integration!")
        print("💡 Set ANTHROPIC_API_KEY environment variable to enable full functionality")
    elif success_rate >= 60:
        print("⚠️  PRIORITIZATION AGENT: PARTIAL")
        print("🔧 Core functionality working, some issues to resolve")
    else:
        print("❌ PRIORITIZATION AGENT: FAILED")
        print("🚨 Critical issues detected")

    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())