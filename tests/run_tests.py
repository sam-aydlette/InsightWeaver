#!/usr/bin/env python3
"""
Test Runner for InsightWeaver
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    """Run available test suites"""
    print("InsightWeaver Test Runner")
    print("=" * 30)
    print()
    print("Available tests:")
    print("1. Phase 2 Checkpoint Verification")
    print("2. Prioritization Agent Test")
    print()

    choice = input("Select test to run (1-2): ").strip() or "1"

    if choice == "1":
        print("\nRunning Phase 2 Checkpoint Verification...")
        from test_phase2_checkpoint import main as phase2_main
        asyncio.run(phase2_main())
    elif choice == "2":
        print("\nRunning Prioritization Agent Test...")
        from test_prioritization_agent import main as prioritization_main
        asyncio.run(prioritization_main())
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()