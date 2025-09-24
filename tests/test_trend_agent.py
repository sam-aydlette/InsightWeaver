#!/usr/bin/env python3
"""
Comprehensive end-to-end test for Trend Analysis Agent
Tests the complete 3-stage workflow and validates trend detection
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from colorama import init, Fore, Style
from tabulate import tabulate

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Initialize colorama for colored output
init(autoreset=True)

# Configure logging to show detailed info
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress httpx logging to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)

async def test_trend_analysis():
    """Comprehensive end-to-end test of the trend analysis agent"""

    print("Starting comprehensive trend analysis test...")

    try:
        from src.agents.trend_agent import TrendAnalysisAgent
        from src.database.connection import get_db
        from src.database.models import Article
        from src.analyzers.trend_analyzer import TrendAnalyzer
        print("✓ Imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        raise

    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}COMPREHENSIVE TREND ANALYSIS AGENT TEST")
    print(f"{Fore.CYAN}{'='*80}\n")

    # Test configuration
    test_results = {
        "stage_1_success": False,
        "stage_2_success": False,
        "stage_3_success": False,
        "end_to_end_success": False,
        "performance_metrics": {},
        "error_handling_tests": {},
        "data_quality_metrics": {}
    }

    # Initialize agent
    print(f"{Fore.YELLOW}Initializing Trend Analysis Agent...")
    agent = TrendAnalysisAgent()
    analyzer = TrendAnalyzer()

    # Get sample of recent articles
    print(f"{Fore.YELLOW}Fetching articles from last 30 days...")
    with get_db() as db:
        article_count = db.query(Article).count()
        recent_count = agent.get_recent_articles(days=30).__len__()

    print(f"{Fore.GREEN}✓ Found {recent_count:,} articles from last 30 days (out of {article_count:,} total)")

    # Check for test mode
    test_mode = os.getenv("TEST_MODE", "quick")
    if test_mode == "quick":
        limit = 100  # Quick test with 100 articles
        print(f"{Fore.YELLOW}Running in QUICK TEST MODE with {limit} articles")
    elif test_mode == "mini":
        limit = 50   # Mini test for development
        print(f"{Fore.YELLOW}Running in MINI TEST MODE with {limit} articles")
    else:
        limit = 1000  # Full test with 1000 articles
        print(f"{Fore.YELLOW}Running in FULL TEST MODE with {limit} articles")

    # Get articles for testing
    print(f"\n{Fore.YELLOW}Preparing test dataset...")
    articles = agent.get_recent_articles(days=30, limit=limit)
    print(f"{Fore.GREEN}✓ Retrieved {len(articles)} articles for testing")

    # STAGE 1 TEST: Local trend categorization
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}STAGE 1 TEST: LOCAL TREND CATEGORIZATION")
    print(f"{Fore.CYAN}{'='*80}")

    stage1_start = datetime.now()
    try:
        # Prepare articles data like the real workflow does
        articles_data = []
        with get_db() as db:
            for article in articles[:limit]:  # Use limit to avoid memory issues
                article = db.merge(article)
                from datetime import timezone
                fetched_at = article.fetched_at.replace(tzinfo=timezone.utc) if article.fetched_at.tzinfo is None else article.fetched_at
                article_age_days = (datetime.now(timezone.utc) - fetched_at).total_seconds() / (24 * 3600)

                articles_data.append({
                    "id": article.id,
                    "title": article.title or "No title",
                    "content": (article.normalized_content or article.description or "")[:800],
                    "age_days": round(article_age_days, 1),
                })

        # Test local categorization
        trend_groups = analyzer.categorize_articles_by_trends(articles_data)
        stage1_time = (datetime.now() - stage1_start).total_seconds()

        print(f"{Fore.GREEN}✓ Stage 1 completed in {stage1_time:.2f} seconds")
        print(f"{Fore.GREEN}✓ Categorized {len(articles_data)} articles into {len(trend_groups)} trend groups")

        # Detailed stage 1 results
        valid_trends = {k: v for k, v in trend_groups.items() if len(v) >= 3}
        print(f"{Fore.GREEN}✓ Found {len(valid_trends)} trends with sufficient coverage (3+ articles)")

        stage1_table = []
        total_categorized = 0
        for trend_name, trend_articles in sorted(trend_groups.items(), key=lambda x: len(x[1]), reverse=True):
            coverage = len(trend_articles)
            total_categorized += coverage
            status = "✓" if coverage >= 3 else "○"
            color = Fore.GREEN if coverage >= 3 else Fore.WHITE
            stage1_table.append([
                f"{color}{status} {trend_name.replace('_', ' ').title()[:35]}",
                f"{color}{coverage}",
                f"{color}{coverage/len(articles_data)*100:.1f}%"
            ])

        print(f"\n{Fore.CYAN}Stage 1 Categorization Results:")
        headers = ["Trend Category", "Articles", "Coverage"]
        print(tabulate(stage1_table[:15], headers=headers, tablefmt="grid"))

        categorization_rate = (total_categorized / len(articles_data)) * 100
        print(f"\n{Fore.GREEN}✓ Overall categorization rate: {categorization_rate:.1f}% ({total_categorized}/{len(articles_data)} articles)")

        test_results["stage_1_success"] = True
        test_results["performance_metrics"]["stage1_time"] = stage1_time
        test_results["data_quality_metrics"]["categorization_rate"] = categorization_rate
        test_results["data_quality_metrics"]["valid_trends"] = len(valid_trends)

    except Exception as e:
        print(f"{Fore.RED}❌ Stage 1 failed: {e}")
        test_results["stage_1_success"] = False
        test_results["error_handling_tests"]["stage1_error"] = str(e)

    # STAGE 2 TEST: Haiku pro/against classification
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}STAGE 2 TEST: HAIKU PRO/AGAINST CLASSIFICATION")
    print(f"{Fore.CYAN}{'='*80}")

    stage2_start = datetime.now()
    stage2_stats = {"total_articles": 0, "neutral_fallbacks": 0, "missing_fallbacks": 0, "api_calls": 0}

    try:
        if test_results["stage_1_success"]:
            # Test only trends with sufficient coverage
            filtered_groups = {k: v for k, v in trend_groups.items() if len(v) >= 3}
            print(f"{Fore.YELLOW}Testing Stage 2 on {len(filtered_groups)} trends...")

            # Test a single trend to validate Stage 2 functionality
            if filtered_groups:
                test_trend = list(filtered_groups.keys())[0]
                test_articles = filtered_groups[test_trend][:15]  # Limit for testing

                print(f"{Fore.YELLOW}Testing with trend: {test_trend} ({len(test_articles)} articles)")

                trend_info = analyzer.get_trend_info(test_trend)
                if trend_info:
                    prompt = agent._create_pro_against_prompt(test_trend, trend_info["description"])

                    # Test API call
                    result = await agent.haiku_client.analyze_trend_batch(
                        system_prompt=prompt,
                        articles_data=test_articles,
                        batch_size=15
                    )

                    stage2_stats["api_calls"] = 1
                    stage2_stats["total_articles"] = len(test_articles)

                    if result:
                        print(f"{Fore.GREEN}✓ API call successful - received {len(result)} stance classifications")

                        # Analyze stance distribution
                        stances = [item.get("stance", "UNKNOWN") for item in result]
                        stance_dist = {
                            "SUPPORTING": stances.count("SUPPORTING"),
                            "OPPOSING": stances.count("OPPOSING"),
                            "NEUTRAL": stances.count("NEUTRAL")
                        }

                        stage2_stats["neutral_fallbacks"] = stance_dist["NEUTRAL"]

                        print(f"{Fore.GREEN}✓ Stance distribution: {stance_dist}")

                        # Test binary prompt effectiveness
                        if stance_dist["NEUTRAL"] == 0:
                            print(f"{Fore.GREEN}✓ Binary prompt working perfectly - no NEUTRAL responses")
                        else:
                            neutral_rate = (stance_dist["NEUTRAL"] / len(result)) * 100
                            print(f"{Fore.YELLOW}⚠ Binary prompt {100-neutral_rate:.1f}% effective - {stance_dist['NEUTRAL']} NEUTRAL responses")

                        test_results["stage_2_success"] = True
                    else:
                        print(f"{Fore.RED}❌ API call returned empty result")
                        test_results["stage_2_success"] = False
                else:
                    print(f"{Fore.RED}❌ Could not get trend info for {test_trend}")
                    test_results["stage_2_success"] = False
            else:
                print(f"{Fore.YELLOW}⚠ No trends with sufficient coverage for Stage 2 testing")
                test_results["stage_2_success"] = False
        else:
            print(f"{Fore.RED}❌ Skipping Stage 2 - Stage 1 failed")
            test_results["stage_2_success"] = False

        stage2_time = (datetime.now() - stage2_start).total_seconds()
        test_results["performance_metrics"]["stage2_time"] = stage2_time
        test_results["performance_metrics"]["stage2_stats"] = stage2_stats

    except Exception as e:
        print(f"{Fore.RED}❌ Stage 2 failed: {e}")
        test_results["stage_2_success"] = False
        test_results["error_handling_tests"]["stage2_error"] = str(e)

    # STAGE 3 TEST: Trend direction calculation
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}STAGE 3 TEST: TREND DIRECTION CALCULATION")
    print(f"{Fore.CYAN}{'='*80}")

    stage3_start = datetime.now()
    try:
        # Create mock trend stances for testing calculation logic
        mock_trend_stances = {
            "test_trend_gaining": [
                {"stance": "SUPPORTING", "confidence": 0.8},
                {"stance": "SUPPORTING", "confidence": 0.7},
                {"stance": "SUPPORTING", "confidence": 0.9},
                {"stance": "OPPOSING", "confidence": 0.6},
            ],
            "test_trend_losing": [
                {"stance": "OPPOSING", "confidence": 0.8},
                {"stance": "OPPOSING", "confidence": 0.7},
                {"stance": "SUPPORTING", "confidence": 0.5},
            ],
            "test_trend_neutral": [
                {"stance": "SUPPORTING", "confidence": 0.6},
                {"stance": "OPPOSING", "confidence": 0.6},
                {"stance": "SUPPORTING", "confidence": 0.5},
                {"stance": "OPPOSING", "confidence": 0.5},
            ]
        }

        # Test direction calculation logic
        trend_directions = agent._calculate_trend_directions(mock_trend_stances)

        print(f"{Fore.GREEN}✓ Successfully calculated directions for {len(trend_directions)} test trends")

        # Validate calculation logic
        stage3_table = []
        logic_tests_passed = 0
        for trend in trend_directions:
            expected = {
                "test_trend_gaining": "GAINING",
                "test_trend_losing": "LOSING",
                "test_trend_neutral": "NEUTRAL"
            }.get(trend["trend"], "UNKNOWN")

            actual = trend["direction"]
            test_passed = actual == expected
            if test_passed:
                logic_tests_passed += 1

            status = "✓" if test_passed else "❌"
            color = Fore.GREEN if test_passed else Fore.RED

            stage3_table.append([
                f"{color}{trend['trend']}",
                f"{color}{actual}",
                f"{color}{expected}",
                f"{color}{status}",
                f"{color}{trend['confidence']:.2f}",
                f"{color}{trend['article_count']}"
            ])

        print(f"\n{Fore.CYAN}Stage 3 Logic Validation:")
        headers = ["Test Trend", "Calculated", "Expected", "Pass", "Confidence", "Articles"]
        print(tabulate(stage3_table, headers=headers, tablefmt="grid"))

        logic_success_rate = (logic_tests_passed / len(trend_directions)) * 100
        print(f"\n{Fore.GREEN}✓ Direction calculation logic: {logic_success_rate:.0f}% accurate ({logic_tests_passed}/{len(trend_directions)} tests passed)")

        test_results["stage_3_success"] = logic_tests_passed == len(trend_directions)
        test_results["data_quality_metrics"]["direction_logic_accuracy"] = logic_success_rate

        stage3_time = (datetime.now() - stage3_start).total_seconds()
        test_results["performance_metrics"]["stage3_time"] = stage3_time

    except Exception as e:
        print(f"{Fore.RED}❌ Stage 3 failed: {e}")
        test_results["stage_3_success"] = False
        test_results["error_handling_tests"]["stage3_error"] = str(e)

    # END-TO-END TEST: Full workflow
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}END-TO-END TEST: FULL WORKFLOW")
    print(f"{Fore.CYAN}{'='*80}")

    print(f"\n{Fore.YELLOW}Running 3-stage trend analysis workflow...")
    print(f"{Fore.BLUE}  Stage 1: Local trend categorization (spaCy)")
    print(f"{Fore.BLUE}  Stage 2: Haiku pro/against classification")
    print(f"{Fore.BLUE}  Stage 3: 6-month trend direction calculation\n")

    e2e_start = datetime.now()
    try:
        results = await agent.run_analysis(days=30, limit=limit)
        e2e_time = (datetime.now() - e2e_start).total_seconds()

        # Extract results
        summary = results.get("summary", {})
        trend_analysis = results.get("trend_analysis", [])

        print(f"\n{Fore.GREEN}✓ End-to-end analysis completed in {e2e_time:.1f} seconds")
        print(f"{Fore.GREEN}✓ Processed {results.get('articles_processed', 0):,} articles")
        print(f"{Fore.GREEN}✓ Analyzed {summary.get('trends_analyzed', 0)} trend categories")
        print(f"{Fore.GREEN}✓ Detected {summary.get('trends_detected', 0)} trends with direction\n")

        test_results["end_to_end_success"] = True
        test_results["performance_metrics"]["e2e_time"] = e2e_time

    except Exception as e:
        print(f"{Fore.RED}❌ End-to-end test failed: {e}")
        test_results["end_to_end_success"] = False
        test_results["error_handling_tests"]["e2e_error"] = str(e)

    # COMPREHENSIVE TEST SUMMARY
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}COMPREHENSIVE TEST SUMMARY")
    print(f"{Fore.CYAN}{'='*80}")

    # Calculate overall success
    all_stages_passed = (
        test_results["stage_1_success"] and
        test_results["stage_2_success"] and
        test_results["stage_3_success"] and
        test_results["end_to_end_success"]
    )

    # Overall status
    overall_status = "PASS" if all_stages_passed else "PARTIAL"
    overall_color = Fore.GREEN if all_stages_passed else Fore.YELLOW

    print(f"\n{overall_color}OVERALL TEST STATUS: {overall_status}")
    print(f"{overall_color}{'='*50}")

    # Stage-by-stage results
    stage_results = [
        ["Stage 1 (Local Categorization)", "✓ PASS" if test_results["stage_1_success"] else "❌ FAIL"],
        ["Stage 2 (API Classification)", "✓ PASS" if test_results["stage_2_success"] else "❌ FAIL"],
        ["Stage 3 (Direction Calculation)", "✓ PASS" if test_results["stage_3_success"] else "❌ FAIL"],
        ["End-to-End Workflow", "✓ PASS" if test_results["end_to_end_success"] else "❌ FAIL"]
    ]

    print(f"\n{Fore.CYAN}Test Results by Stage:")
    print(tabulate(stage_results, headers=["Component", "Status"], tablefmt="grid"))

    # Performance metrics
    if test_results["performance_metrics"]:
        print(f"\n{Fore.CYAN}Performance Metrics:")
        perf_table = []
        total_time = 0

        for stage, time_val in test_results["performance_metrics"].items():
            if isinstance(time_val, (int, float)):
                perf_table.append([stage.replace("_", " ").title(), f"{time_val:.2f}s"])
                total_time += time_val

        if perf_table:
            perf_table.append(["Total Test Time", f"{total_time:.2f}s"])
            print(tabulate(perf_table, headers=["Metric", "Value"], tablefmt="grid"))

    # Data quality metrics
    if test_results["data_quality_metrics"]:
        print(f"\n{Fore.CYAN}Data Quality Metrics:")
        quality_table = []
        for metric, value in test_results["data_quality_metrics"].items():
            if isinstance(value, (int, float)):
                if "rate" in metric or "accuracy" in metric:
                    quality_table.append([metric.replace("_", " ").title(), f"{value:.1f}%"])
                else:
                    quality_table.append([metric.replace("_", " ").title(), f"{value}"])

        if quality_table:
            print(tabulate(quality_table, headers=["Metric", "Value"], tablefmt="grid"))

    # Error summary
    if test_results["error_handling_tests"]:
        print(f"\n{Fore.RED}Errors Encountered:")
        for stage, error in test_results["error_handling_tests"].items():
            print(f"  {Fore.RED}• {stage}: {error[:100]}...")

    # Success criteria evaluation
    print(f"\n{Fore.CYAN}Success Criteria Evaluation:")
    criteria_table = []

    # Stage 1 criteria
    stage1_ok = test_results["data_quality_metrics"].get("categorization_rate", 0) > 80
    criteria_table.append([
        "Stage 1: >80% categorization rate",
        "✓ PASS" if stage1_ok else "❌ FAIL",
        f"{test_results['data_quality_metrics'].get('categorization_rate', 0):.1f}%"
    ])

    # Stage 2 criteria
    stage2_ok = test_results["stage_2_success"]
    api_calls = test_results["performance_metrics"].get("stage2_stats", {}).get("api_calls", 0)
    criteria_table.append([
        "Stage 2: API classification working",
        "✓ PASS" if stage2_ok else "❌ FAIL",
        f"{api_calls} API calls"
    ])

    # Stage 3 criteria
    stage3_ok = test_results["data_quality_metrics"].get("direction_logic_accuracy", 0) == 100
    criteria_table.append([
        "Stage 3: 100% logic accuracy",
        "✓ PASS" if stage3_ok else "❌ FAIL",
        f"{test_results['data_quality_metrics'].get('direction_logic_accuracy', 0):.0f}%"
    ])

    # End-to-end criteria
    e2e_ok = test_results["end_to_end_success"]
    processed = results.get('articles_processed', 0) if 'results' in locals() else 0
    criteria_table.append([
        "End-to-End: Complete workflow",
        "✓ PASS" if e2e_ok else "❌ FAIL",
        f"{processed} articles processed"
    ])

    print(tabulate(criteria_table, headers=["Success Criteria", "Status", "Details"], tablefmt="grid"))

    # Recommendations
    print(f"\n{Fore.CYAN}Recommendations:")
    if not test_results["stage_1_success"]:
        print(f"{Fore.YELLOW}• Fix Stage 1 local categorization issues")
    if not test_results["stage_2_success"]:
        print(f"{Fore.YELLOW}• Check API connectivity and prompt effectiveness")
    if not test_results["stage_3_success"]:
        print(f"{Fore.YELLOW}• Review trend direction calculation logic")
    if test_results["error_handling_tests"]:
        print(f"{Fore.YELLOW}• Address error handling for failed components")

    if all_stages_passed:
        print(f"{Fore.GREEN}• All systems operational - ready for production")
    else:
        print(f"{Fore.YELLOW}• Resolve failing components before production deployment")

    print(f"\n{Fore.CYAN}{'='*80}")
    final_status = "COMPREHENSIVE TEST COMPLETED SUCCESSFULLY" if all_stages_passed else "COMPREHENSIVE TEST COMPLETED WITH ISSUES"
    final_color = Fore.GREEN if all_stages_passed else Fore.YELLOW
    print(f"{final_color}{final_status}")
    print(f"{Fore.CYAN}{'='*80}\n")

    return {
        "test_results": test_results,
        "overall_success": all_stages_passed,
        "workflow_results": results if 'results' in locals() else None
    }

if __name__ == "__main__":
    print("Starting comprehensive trend analysis test...")

    # Check for required environment variables
    from dotenv import load_dotenv
    load_dotenv()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print(f"{Fore.RED}Error: ANTHROPIC_API_KEY not found in environment")
        print(f"{Fore.YELLOW}Please set your API key in the .env file")
        exit(1)

    print("✓ Environment and API key validated")

    # Run the test
    try:
        results = asyncio.run(test_trend_analysis())
        if results["overall_success"]:
            print("✅ All tests passed!")
            exit(0)
        else:
            print("⚠️ Some tests failed - check output above")
            exit(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)