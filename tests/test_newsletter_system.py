#!/usr/bin/env python3
"""
Test Newsletter System
Comprehensive validation of Phase 4 intelligence briefing capabilities
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from colorama import init, Fore

# Initialize colorama
init(autoreset=True)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.newsletter.newsletter_system import NewsletterSystem

async def test_newsletter_system():
    """Test the complete newsletter system"""
    print(f"{Fore.CYAN}InsightWeaver Newsletter System Test")
    print(f"{Fore.CYAN}{'='*60}")

    test_results = {
        "system_initialization": False,
        "daily_brief_generation": False,
        "weekly_analysis_generation": False,
        "template_rendering": False,
        "email_system_check": False,
        "overall_success": False,
        "performance_metrics": {},
        "content_quality": {}
    }

    try:
        # Stage 1: System Initialization
        print(f"\n{Fore.YELLOW}Stage 1: Newsletter System Initialization")
        print("-" * 40)

        system = NewsletterSystem()
        print(f"{Fore.GREEN}✓ Newsletter system initialized")
        test_results["system_initialization"] = True

        # Stage 2: System Health Check
        print(f"\n{Fore.YELLOW}Stage 2: System Health Check")
        print("-" * 40)

        health_check = await system.test_system()
        print(f"System Status: {health_check['overall_status']}")

        if health_check["content_engine"]:
            print(f"{Fore.GREEN}✓ Content engine operational")

        if health_check["template_rendering"]:
            print(f"{Fore.GREEN}✓ Template rendering operational")

        email_status = health_check.get("email_system", False)
        if email_status == True:
            print(f"{Fore.GREEN}✓ Email system fully operational")
            test_results["email_system_check"] = True
        elif email_status == "not_configured":
            print(f"{Fore.YELLOW}⚠️ Email system not configured (local-only mode)")
            test_results["email_system_check"] = "local_only"
        else:
            print(f"{Fore.RED}❌ Email system failed")

        # Stage 3: Daily Brief Generation
        print(f"\n{Fore.YELLOW}Stage 3: Daily Brief Generation")
        print("-" * 40)

        daily_start = datetime.now()
        test_date = datetime.now() - timedelta(days=1)  # Yesterday's data

        daily_result = await system.generate_daily_brief(
            date=test_date,
            save_local=True,
            send_email=False  # Don't send during testing
        )

        daily_duration = (datetime.now() - daily_start).total_seconds()

        if daily_result["success"]:
            print(f"{Fore.GREEN}✓ Daily brief generated successfully")
            print(f"  • Articles processed: {daily_result['article_count']}")
            print(f"  • Priority items: {daily_result['priority_count']}")
            print(f"  • Trends detected: {daily_result['trend_count']}")
            print(f"  • Generation time: {daily_duration:.1f}s")
            if daily_result.get("local_saved"):
                print(f"  • Saved to: {daily_result['local_path']}")

            test_results["daily_brief_generation"] = True
            test_results["performance_metrics"]["daily_generation_time"] = daily_duration
            test_results["content_quality"]["daily_articles"] = daily_result["article_count"]
            test_results["content_quality"]["daily_priorities"] = daily_result["priority_count"]
        else:
            print(f"{Fore.RED}❌ Daily brief generation failed")
            if "error" in daily_result:
                print(f"  Error: {daily_result['error']}")

        # Stage 4: Weekly Analysis Generation
        print(f"\n{Fore.YELLOW}Stage 4: Weekly Analysis Generation")
        print("-" * 40)

        weekly_start = datetime.now()

        weekly_result = await system.generate_weekly_analysis(
            end_date=datetime.now(),
            save_local=True,
            send_email=False  # Don't send during testing
        )

        weekly_duration = (datetime.now() - weekly_start).total_seconds()

        if weekly_result["success"]:
            print(f"{Fore.GREEN}✓ Weekly analysis generated successfully")
            print(f"  • Total articles analyzed: {weekly_result['total_articles']}")
            print(f"  • Trends tracked: {weekly_result['trend_count']}")
            print(f"  • Generation time: {weekly_duration:.1f}s")
            if weekly_result.get("local_saved"):
                print(f"  • Saved to: {weekly_result['local_path']}")

            test_results["weekly_analysis_generation"] = True
            test_results["performance_metrics"]["weekly_generation_time"] = weekly_duration
            test_results["content_quality"]["weekly_articles"] = weekly_result["total_articles"]
            test_results["content_quality"]["weekly_trends"] = weekly_result["trend_count"]
        else:
            print(f"{Fore.RED}❌ Weekly analysis generation failed")
            if "error" in weekly_result:
                print(f"  Error: {weekly_result['error']}")

        # Stage 5: Template Rendering Test
        print(f"\n{Fore.YELLOW}Stage 5: Template Rendering Validation")
        print("-" * 40)

        if test_results["daily_brief_generation"]:
            try:
                daily_preview = await system.preview_daily_brief(test_date)
                if daily_preview and len(daily_preview) > 1000:
                    print(f"{Fore.GREEN}✓ Daily brief template rendering: {len(daily_preview)} characters")
                    test_results["template_rendering"] = True
                else:
                    print(f"{Fore.RED}❌ Daily brief template too short or empty")
            except Exception as e:
                print(f"{Fore.RED}❌ Daily brief template error: {e}")

        if test_results["weekly_analysis_generation"]:
            try:
                weekly_preview = await system.preview_weekly_analysis()
                if weekly_preview and len(weekly_preview) > 1000:
                    print(f"{Fore.GREEN}✓ Weekly analysis template rendering: {len(weekly_preview)} characters")
                else:
                    print(f"{Fore.RED}❌ Weekly analysis template too short or empty")
            except Exception as e:
                print(f"{Fore.RED}❌ Weekly analysis template error: {e}")

        # Overall Assessment
        print(f"\n{Fore.YELLOW}Stage 6: Overall System Assessment")
        print("-" * 40)

        core_systems = [
            test_results["system_initialization"],
            test_results["daily_brief_generation"],
            test_results["weekly_analysis_generation"],
            test_results["template_rendering"]
        ]

        if all(core_systems):
            test_results["overall_success"] = True
            print(f"{Fore.GREEN}✅ ALL TESTS PASSED - Newsletter system fully operational")
        else:
            failed_systems = []
            if not test_results["system_initialization"]:
                failed_systems.append("System Initialization")
            if not test_results["daily_brief_generation"]:
                failed_systems.append("Daily Brief Generation")
            if not test_results["weekly_analysis_generation"]:
                failed_systems.append("Weekly Analysis Generation")
            if not test_results["template_rendering"]:
                failed_systems.append("Template Rendering")

            print(f"{Fore.RED}❌ SOME TESTS FAILED")
            print(f"Failed systems: {', '.join(failed_systems)}")

    except Exception as e:
        print(f"{Fore.RED}❌ Newsletter system test failed with exception: {e}")
        test_results["error"] = str(e)

    # Test Summary
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Newsletter System Test Summary")
    print(f"{Fore.CYAN}{'='*60}")

    # Results breakdown
    results_summary = [
        ("System Initialization", test_results["system_initialization"]),
        ("Daily Brief Generation", test_results["daily_brief_generation"]),
        ("Weekly Analysis Generation", test_results["weekly_analysis_generation"]),
        ("Template Rendering", test_results["template_rendering"]),
        ("Email System", test_results["email_system_check"])
    ]

    for test_name, result in results_summary:
        if result == True:
            print(f"{Fore.GREEN}✅ {test_name}: PASSED")
        elif result == "local_only":
            print(f"{Fore.YELLOW}⚠️ {test_name}: LOCAL ONLY")
        elif result == False:
            print(f"{Fore.RED}❌ {test_name}: FAILED")

    # Performance metrics
    if test_results["performance_metrics"]:
        print(f"\n{Fore.BLUE}Performance Metrics:")
        for metric, value in test_results["performance_metrics"].items():
            print(f"  • {metric}: {value:.1f}s")

    # Content quality
    if test_results["content_quality"]:
        print(f"\n{Fore.BLUE}Content Quality:")
        for metric, value in test_results["content_quality"].items():
            print(f"  • {metric}: {value}")

    # Final recommendation
    print(f"\n{Fore.CYAN}Recommendation:")
    if test_results["overall_success"]:
        if test_results["email_system_check"] == True:
            print(f"{Fore.GREEN}System is production-ready with full email capabilities")
        else:
            print(f"{Fore.YELLOW}System is production-ready in local-only mode")
            print(f"{Fore.YELLOW}Configure email settings for full functionality")
    else:
        print(f"{Fore.RED}System requires fixes before production deployment")

    return test_results

async def main():
    """Main test function"""
    results = await test_newsletter_system()

    # Exit with appropriate code
    if results["overall_success"]:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())