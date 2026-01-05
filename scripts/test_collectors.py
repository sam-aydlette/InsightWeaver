#!/usr/bin/env python3
"""
Test script for API data collectors
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def load_decision_context():
    """Load decision context for relevance scoring"""
    decision_file = Path("config/context_modules/core/decision_context.json")
    if decision_file.exists():
        with open(decision_file) as f:
            return json.load(f)
    return None


def test_collectors():
    """Test all data collectors"""
    from src.collectors.manager import CollectorManager

    logger.info("=== Testing InsightWeaver Data Collectors ===\n")

    # Load decision context
    decision_context = load_decision_context()
    if decision_context:
        logger.info(
            f"Loaded decision context with {len(decision_context.get('active_decisions', []))} active decisions"
        )
    else:
        logger.warning("No decision context found")

    # Initialize collector manager
    manager = CollectorManager()
    manager.initialize_collectors(decision_context)

    logger.info(f"\nInitialized {len(manager.collectors)} collectors:")
    for name in manager.collectors:
        logger.info(f"  - {name}")

    # Run all collectors
    logger.info("\n=== Running All Collectors ===\n")
    summary = manager.collect_all(decision_context=decision_context, force=True)

    logger.info("\n=== Collection Summary ===")
    logger.info(f"Total collectors: {summary['total_collectors']}")
    logger.info(f"Collectors run: {summary['collectors_run']}")
    logger.info(f"Collectors skipped: {summary['collectors_skipped']}")
    logger.info(f"Collectors failed: {summary['collectors_failed']}")
    logger.info(f"Total items collected: {summary['total_items_collected']}")

    logger.info("\n=== Individual Results ===")
    for name, result in summary["results"].items():
        if result.get("success"):
            logger.info(f"\n{name}:")
            logger.info(f"  New items: {result.get('new_items', 0)}")
            logger.info(f"  Updated items: {result.get('updated_items', 0)}")
            logger.info(f"  Skipped items: {result.get('skipped_items', 0)}")
        else:
            logger.error(f"\n{name}: FAILED")
            logger.error(f"  Error: {result.get('error')}")

    # Get collection status
    logger.info("\n=== Collection Status ===")
    status = manager.get_collection_status()
    for source_name, source_status in status.items():
        logger.info(f"\n{source_name}:")
        logger.info(f"  Type: {source_status['source_type']}")
        logger.info(f"  Active: {source_status['is_active']}")
        logger.info(f"  Last fetched: {source_status['last_fetched']}")
        logger.info(f"  Error count: {source_status['error_count']}")
        if source_status["last_error"]:
            logger.info(f"  Last error: {source_status['last_error']}")


if __name__ == "__main__":
    try:
        test_collectors()
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)
