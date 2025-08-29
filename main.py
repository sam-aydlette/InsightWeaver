#!/usr/bin/env python3
"""
InsightWeaver - An app that curates information from a wide range of reputable sources 
and creates custom daily reporting for me on events and trends that I care about.
"""

import asyncio
import argparse
import logging
from datetime import datetime

from src.config.settings import Settings
from src.collectors.feed_collector import FeedCollector
from src.analysis.intelligence_engine import IntelligenceEngine
from src.briefing.generator import BriefingGenerator
from src.briefing.email_sender import EmailSender
from src.data.database import DatabaseManager
from src.utils.logger import setup_logging


async def generate_briefing():
    """Generate and send the daily intelligence briefing"""
    logger = logging.getLogger(__name__)
    logger.info("Starting daily intelligence briefing generation")
    
    try:
        # Initialize components
        settings = Settings()
        db_manager = DatabaseManager(settings.database_path)
        feed_collector = FeedCollector(settings, db_manager)
        intelligence_engine = IntelligenceEngine(settings, db_manager)
        briefing_generator = BriefingGenerator(settings, db_manager)
        email_sender = EmailSender(settings)
        
        # Collect latest articles
        logger.info("Collecting articles from RSS feeds")
        await feed_collector.collect_all_feeds()
        
        # Generate intelligence analysis
        logger.info("Generating intelligence analysis")
        analysis = await intelligence_engine.generate_analysis()
        
        # Create briefing
        logger.info("Creating briefing document")
        briefing_html = await briefing_generator.generate_briefing(analysis)
        
        # Send email
        logger.info("Sending briefing email")
        await email_sender.send_briefing(briefing_html)
        
        logger.info("Daily briefing completed successfully")
        
    except Exception as e:
        logger.error(f"Error generating briefing: {e}", exc_info=True)
        raise


async def main():
    parser = argparse.ArgumentParser(description="InsightWeaver Intelligence Briefing System")
    parser.add_argument("--config", default="config.yaml", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--dry-run", action="store_true", help="Generate briefing without sending email")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    if args.dry_run:
        logging.getLogger(__name__).info("Running in dry-run mode")
    
    await generate_briefing()


if __name__ == "__main__":
    asyncio.run(main())