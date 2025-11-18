#!/usr/bin/env python3
"""
Scheduled Report Generator
Runs daily intelligence report generation and optional maintenance tasks
Called by systemd timer or cron
"""

import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import settings
from src.newsletter.newsletter_system import NewsletterSystem
from src.maintenance.data_retention import cleanup_old_data


# Configure logging
log_file = project_root / "data" / "logs" / f"scheduled_report_{datetime.now().strftime('%Y%m%d')}.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also log to console for systemd journal
    ]
)
logger = logging.getLogger(__name__)


async def run_scheduled_tasks():
    """Execute scheduled tasks: report generation and maintenance"""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Starting scheduled tasks")
    logger.info("=" * 60)

    results = {
        "started_at": start_time.isoformat(),
        "report_generated": False,
        "cleanup_performed": False,
        "errors": []
    }

    try:
        # 1. Generate daily report (if enabled)
        if settings.daily_report_enabled:
            logger.info("Generating daily intelligence report...")
            newsletter = NewsletterSystem()

            try:
                report_result = await newsletter.generate_report(
                    hours=settings.daily_report_hours,
                    save_local=True,
                    send_email=True
                )

                if report_result.get("success"):
                    results["report_generated"] = True
                    results["report_details"] = {
                        "articles_analyzed": report_result.get("articles_analyzed"),
                        "duration_hours": report_result.get("duration_hours"),
                        "local_path": report_result.get("local_path"),
                        "email_sent": report_result.get("email_sent")
                    }
                    logger.info(
                        f"Report generated successfully: {report_result.get('articles_analyzed')} articles, "
                        f"email_sent={report_result.get('email_sent')}"
                    )
                else:
                    error_msg = f"Report generation failed: {report_result.get('error')}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

            except Exception as e:
                error_msg = f"Exception during report generation: {e}"
                logger.error(error_msg, exc_info=True)
                results["errors"].append(error_msg)
        else:
            logger.info("Daily report disabled in settings, skipping")

        # 2. Run data cleanup (if enabled)
        if settings.auto_cleanup_enabled:
            logger.info("Running data retention cleanup...")
            try:
                cleanup_result = cleanup_old_data(dry_run=False)
                results["cleanup_performed"] = True
                results["cleanup_details"] = {
                    "articles_deleted": cleanup_result["articles"].get("deleted", 0),
                    "syntheses_deleted": cleanup_result["syntheses"].get("deleted", 0),
                    "space_freed_mb": cleanup_result.get("total_freed_mb", 0)
                }
                logger.info(
                    f"Cleanup complete: {cleanup_result['articles'].get('deleted', 0)} articles, "
                    f"{cleanup_result['syntheses'].get('deleted', 0)} syntheses deleted "
                    f"(~{cleanup_result.get('total_freed_mb', 0)} MB freed)"
                )
            except Exception as e:
                error_msg = f"Exception during cleanup: {e}"
                logger.error(error_msg, exc_info=True)
                results["errors"].append(error_msg)
        else:
            logger.info("Auto-cleanup disabled in settings, skipping")

    except Exception as e:
        error_msg = f"Unexpected error in scheduled tasks: {e}"
        logger.error(error_msg, exc_info=True)
        results["errors"].append(error_msg)

    # Log summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    results["completed_at"] = end_time.isoformat()
    results["duration_seconds"] = duration

    logger.info("=" * 60)
    logger.info("Scheduled tasks completed")
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info(f"Report generated: {results['report_generated']}")
    logger.info(f"Cleanup performed: {results['cleanup_performed']}")
    if results["errors"]:
        logger.error(f"Errors encountered: {len(results['errors'])}")
        for error in results["errors"]:
            logger.error(f"  - {error}")
    logger.info("=" * 60)

    # Exit with error code if there were failures
    if results["errors"]:
        sys.exit(1)
    else:
        sys.exit(0)


def main():
    """Main entry point"""
    try:
        asyncio.run(run_scheduled_tasks())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
