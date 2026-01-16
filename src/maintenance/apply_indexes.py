"""
Database Index Migration Script
Applies new indexes to existing database for query optimization
"""

import logging

from sqlalchemy import inspect, text

from ..database.connection import engine

logger = logging.getLogger(__name__)


def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index already exists"""
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def apply_indexes(dry_run: bool = False):
    """
    Apply new database indexes for query optimization

    Args:
        dry_run: If True, only show what would be created
    """

    # Define indexes to create
    indexes = [
        # Articles table - composite indexes for critical queries
        {
            "table": "articles",
            "name": "idx_articles_filtered_fetched",
            "sql": "CREATE INDEX idx_articles_filtered_fetched ON articles(filtered, fetched_at)",
        },
        {
            "table": "articles",
            "name": "idx_articles_filtered_published",
            "sql": "CREATE INDEX idx_articles_filtered_published ON articles(filtered, published_date)",
        },
        # MemoryFact table - indexes for semantic memory queries
        {
            "table": "memory_facts",
            "name": "idx_memory_fact_expires",
            "sql": "CREATE INDEX idx_memory_fact_expires ON memory_facts(expires_at)",
        },
        {
            "table": "memory_facts",
            "name": "idx_memory_fact_confidence",
            "sql": "CREATE INDEX idx_memory_fact_confidence ON memory_facts(confidence)",
        },
        {
            "table": "memory_facts",
            "name": "idx_memory_fact_created",
            "sql": "CREATE INDEX idx_memory_fact_created ON memory_facts(created_at)",
        },
    ]

    results = {"created": [], "skipped": [], "failed": []}

    with engine.connect() as conn:
        for idx in indexes:
            try:
                # Check if index already exists
                if index_exists(idx["table"], idx["name"]):
                    logger.info(f"Index {idx['name']} already exists, skipping")
                    results["skipped"].append(idx["name"])
                    continue

                if dry_run:
                    logger.info(f"Would create index: {idx['name']} on {idx['table']}")
                    results["created"].append(idx["name"])
                else:
                    logger.info(f"Creating index: {idx['name']} on {idx['table']}")
                    conn.execute(text(idx["sql"]))
                    conn.commit()
                    results["created"].append(idx["name"])
                    logger.info(f"Successfully created index: {idx['name']}")

            except Exception as e:
                logger.error(f"Failed to create index {idx['name']}: {e}")
                results["failed"].append({"name": idx["name"], "error": str(e)})

    # Print summary
    print("\n" + "=" * 60)
    print("INDEX MIGRATION SUMMARY")
    print("=" * 60)

    if dry_run:
        print("\nDRY RUN MODE - No changes made")

    if results["created"]:
        print(f"\nIndexes created ({len(results['created'])}):")
        for name in results["created"]:
            print(f"  ✓ {name}")

    if results["skipped"]:
        print(f"\nIndexes skipped (already exist) ({len(results['skipped'])}):")
        for name in results["skipped"]:
            print(f"  - {name}")

    if results["failed"]:
        print(f"\nIndexes failed ({len(results['failed'])}):")
        for item in results["failed"]:
            print(f"  ✗ {item['name']}: {item['error']}")

    print("\n" + "=" * 60)

    return results


if __name__ == "__main__":
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("Running in DRY RUN mode - no changes will be made\n")

    apply_indexes(dry_run=dry_run)
