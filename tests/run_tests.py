#!/usr/bin/env python3
"""
Test Runner for InsightWeaver
Comprehensive test suite for all system components
"""

import asyncio
import sys
import os
from pathlib import Path
from colorama import init, Fore

# Initialize colorama
init(autoreset=True)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    """Run available test suites"""
    print(f"{Fore.CYAN}InsightWeaver Test Runner")
    print(f"{Fore.CYAN}{'='*50}")
    print()
    print("Available test suites:")
    print(f"{Fore.YELLOW}1. Phase 2 Checkpoint Verification")
    print(f"{Fore.YELLOW}2. Prioritization Agent Test")
    print(f"{Fore.YELLOW}3. Trend Analysis Agent Test")
    print(f"{Fore.YELLOW}4. Newsletter System Test")
    print(f"{Fore.YELLOW}5. Run All Tests")
    print()
    print("Test modes for agent tests:")
    print(f"{Fore.BLUE}  • MINI: 50 articles (quick development)")
    print(f"{Fore.BLUE}  • QUICK: 100 articles (standard testing)")
    print(f"{Fore.BLUE}  • FULL: 1000 articles (comprehensive)")
    print()

    choice = input("Select test to run (1-5): ").strip() or "4"

    # Set test mode for agent tests (not for newsletter test)
    if choice in ["2", "3", "5"]:
        print()
        mode_choice = input("Select test mode (mini/quick/full) [quick]: ").strip().lower() or "quick"
        os.environ["TEST_MODE"] = mode_choice
        print(f"{Fore.GREEN}✓ Test mode set to: {mode_choice.upper()}")
        print()

    if choice == "1":
        print(f"\n{Fore.CYAN}Running Phase 2 Checkpoint Verification...")
        from test_phase2_checkpoint import main as phase2_main
        asyncio.run(phase2_main())

    elif choice == "2":
        print(f"\n{Fore.CYAN}Running Prioritization Agent Test...")
        from test_prioritization_agent import main as prioritization_main
        asyncio.run(prioritization_main())

    elif choice == "3":
        print(f"\n{Fore.CYAN}Running Trend Analysis Agent Test...")
        from test_trend_agent import test_trend_analysis
        result = asyncio.run(test_trend_analysis())

        if result["overall_success"]:
            print(f"\n{Fore.GREEN}✅ Trend Analysis Agent Test: ALL PASSED")
        else:
            print(f"\n{Fore.YELLOW}⚠️ Trend Analysis Agent Test: PARTIAL SUCCESS")

    elif choice == "4":
        print(f"\n{Fore.CYAN}Running Newsletter System Test...")
        from test_newsletter_system import test_newsletter_system
        result = asyncio.run(test_newsletter_system())

        if result["overall_success"]:
            print(f"\n{Fore.GREEN}✅ Newsletter System Test: ALL PASSED")
        else:
            print(f"\n{Fore.YELLOW}⚠️ Newsletter System Test: PARTIAL SUCCESS")

    elif choice == "5":
        print(f"\n{Fore.CYAN}Running All Tests...")
        all_passed = True

        # Test 1: Phase 2 Checkpoint
        try:
            print(f"\n{Fore.CYAN}[1/4] Phase 2 Checkpoint Verification...")
            from test_phase2_checkpoint import main as phase2_main
            asyncio.run(phase2_main())
            print(f"{Fore.GREEN}✅ Phase 2 Checkpoint: PASSED")
        except Exception as e:
            print(f"{Fore.RED}❌ Phase 2 Checkpoint: FAILED - {e}")
            all_passed = False

        # Test 2: Prioritization Agent
        try:
            print(f"\n{Fore.CYAN}[2/4] Prioritization Agent Test...")
            from test_prioritization_agent import main as prioritization_main
            asyncio.run(prioritization_main())
            print(f"{Fore.GREEN}✅ Prioritization Agent: PASSED")
        except Exception as e:
            print(f"{Fore.RED}❌ Prioritization Agent: FAILED - {e}")
            all_passed = False

        # Test 3: Trend Analysis Agent
        try:
            print(f"\n{Fore.CYAN}[3/4] Trend Analysis Agent Test...")
            from test_trend_agent import test_trend_analysis
            result = asyncio.run(test_trend_analysis())

            if result["overall_success"]:
                print(f"{Fore.GREEN}✅ Trend Analysis Agent: PASSED")
            else:
                print(f"{Fore.YELLOW}⚠️ Trend Analysis Agent: PARTIAL SUCCESS")
                all_passed = False
        except Exception as e:
            print(f"{Fore.RED}❌ Trend Analysis Agent: FAILED - {e}")
            all_passed = False

        # Test 4: Newsletter System
        try:
            print(f"\n{Fore.CYAN}[4/4] Newsletter System Test...")
            from test_newsletter_system import test_newsletter_system
            result = asyncio.run(test_newsletter_system())

            if result["overall_success"]:
                print(f"{Fore.GREEN}✅ Newsletter System: PASSED")
            else:
                print(f"{Fore.YELLOW}⚠️ Newsletter System: PARTIAL SUCCESS")
                all_passed = False
        except Exception as e:
            print(f"{Fore.RED}❌ Newsletter System: FAILED - {e}")
            all_passed = False

        # Overall summary
        print(f"\n{Fore.CYAN}{'='*50}")
        if all_passed:
            print(f"{Fore.GREEN}🎉 ALL TESTS PASSED - System ready for Phase 4 deployment")
        else:
            print(f"{Fore.YELLOW}⚠️ SOME TESTS FAILED - Review failures above")
        print(f"{Fore.CYAN}{'='*50}")

    else:
        print(f"{Fore.RED}Invalid choice")

def run_specific_test(test_name: str, test_mode: str = "quick"):
    """Run a specific test by name (for programmatic use)"""
    if test_name != "newsletter":
        os.environ["TEST_MODE"] = test_mode

    if test_name == "trend":
        from test_trend_agent import test_trend_analysis
        return asyncio.run(test_trend_analysis())
    elif test_name == "prioritization":
        from test_prioritization_agent import main as prioritization_main
        return asyncio.run(prioritization_main())
    elif test_name == "phase2":
        from test_phase2_checkpoint import main as phase2_main
        return asyncio.run(phase2_main())
    elif test_name == "newsletter":
        from test_newsletter_system import test_newsletter_system
        return asyncio.run(test_newsletter_system())
    else:
        raise ValueError(f"Unknown test: {test_name}")

if __name__ == "__main__":
    main()