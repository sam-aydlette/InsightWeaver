"""
Collector Manager
Orchestrates data collection from all configured API sources
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from .fairfax_calendar import FairfaxCalendarCollector
from .event_monitor import EventMonitorCollector
from .job_market import JobMarketCollector
from .vulncheck_kev import VulnCheckKEVCollector
from ..database.connection import get_db
from ..database.models import APIDataSource

logger = logging.getLogger(__name__)


class CollectorManager:
    """
    Manages and orchestrates all data collectors

    Responsibilities:
    - Load collector configuration
    - Initialize collectors with user context
    - Schedule and execute collections
    - Track collection status and errors
    """

    def __init__(self, config_path: str = "config/api_sources.json"):
        """
        Initialize collector manager

        Args:
            config_path: Path to collector configuration file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.collectors = {}

    def _load_config(self) -> Dict:
        """Load collector configuration from JSON"""
        if not self.config_path.exists():
            logger.warning(f"Collector config not found: {self.config_path}")
            return {'collectors': {}}

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def initialize_collectors(self, decision_context: Optional[Dict] = None) -> None:
        """
        Initialize all enabled collectors

        Args:
            decision_context: User's decision context for relevance scoring
        """
        collector_configs = self.config.get('collectors', {})

        for name, config in collector_configs.items():
            if not config.get('enabled', False):
                logger.info(f"Collector '{name}' is disabled, skipping")
                continue

            try:
                collector = self._create_collector(name, config)
                if collector:
                    self.collectors[name] = {
                        'instance': collector,
                        'config': config
                    }
                    logger.info(f"Initialized collector: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize collector '{name}': {e}")

    def _create_collector(self, name: str, config: Dict) -> Optional[Any]:
        """
        Create collector instance based on configuration

        Args:
            name: Collector name
            config: Collector configuration dict

        Returns:
            Collector instance or None
        """
        class_name = config.get('class')
        collector_config = config.get('config', {})

        if class_name == 'FairfaxCalendarCollector':
            return FairfaxCalendarCollector()

        elif class_name == 'EventMonitorCollector':
            artists = collector_config.get('artists', [])
            app_id = collector_config.get('app_id', 'insightweaver')
            return EventMonitorCollector(artists=artists, app_id=app_id)

        elif class_name == 'JobMarketCollector':
            keywords = collector_config.get('keywords', [])
            location_codes = collector_config.get('location_codes', [])
            return JobMarketCollector(
                keywords=keywords,
                location_codes=location_codes
            )

        elif class_name == 'VulnCheckKEVCollector':
            return VulnCheckKEVCollector()

        else:
            logger.error(f"Unknown collector class: {class_name}")
            return None

    def collect_all(
        self,
        decision_context: Optional[Dict] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Run all collectors that are due for refresh

        Args:
            decision_context: User's decision context for relevance scoring
            force: Force collection even if not due

        Returns:
            Collection summary dict
        """
        if not self.collectors:
            self.initialize_collectors(decision_context)

        summary = {
            'total_collectors': len(self.collectors),
            'collectors_run': 0,
            'collectors_skipped': 0,
            'collectors_failed': 0,
            'total_items_collected': 0,
            'results': {}
        }

        for name, collector_data in self.collectors.items():
            collector = collector_data['instance']
            config = collector_data['config']

            try:
                # Check if collection is due
                if not force and not self._should_collect(collector, config):
                    logger.info(f"Skipping {name} - not due for refresh")
                    summary['collectors_skipped'] += 1
                    continue

                logger.info(f"Running collector: {name}")

                # Run collection
                result = collector.collect_and_store(
                    decision_context=decision_context,
                    max_items=100
                )

                summary['collectors_run'] += 1
                summary['total_items_collected'] += result.get('new_items', 0)
                summary['results'][name] = result

                logger.info(f"Collector '{name}' completed: {result}")

            except Exception as e:
                logger.error(f"Collector '{name}' failed: {e}")
                summary['collectors_failed'] += 1
                summary['results'][name] = {
                    'success': False,
                    'error': str(e)
                }

        return summary

    def _should_collect(self, collector: Any, config: Dict) -> bool:
        """
        Check if collector should run based on last fetch time

        Args:
            collector: Collector instance
            config: Collector configuration

        Returns:
            True if collection is due
        """
        refresh_hours = config.get('refresh_hours', 24)

        with get_db() as session:
            # Find source record
            source = session.query(APIDataSource).filter(
                APIDataSource.name == collector.source_name
            ).first()

            if not source or not source.last_fetched:
                return True  # Never fetched, should run

            # Check if enough time has passed
            next_fetch = source.last_fetched + timedelta(hours=refresh_hours)
            return datetime.utcnow() >= next_fetch

    def get_collection_status(self) -> Dict[str, Any]:
        """
        Get status of all collectors

        Returns:
            Status dict with last fetch times and error counts
        """
        status = {}

        with get_db() as session:
            sources = session.query(APIDataSource).all()

            for source in sources:
                status[source.name] = {
                    'source_type': source.source_type,
                    'is_active': source.is_active,
                    'last_fetched': source.last_fetched.isoformat() if source.last_fetched else None,
                    'error_count': source.error_count,
                    'last_error': source.last_error
                }

        return status

    def run_specific_collector(
        self,
        collector_name: str,
        decision_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Run a specific collector by name

        Args:
            collector_name: Name of collector to run
            decision_context: User's decision context

        Returns:
            Collection result dict
        """
        if collector_name not in self.collectors:
            # Try to initialize if not loaded
            self.initialize_collectors(decision_context)

        if collector_name not in self.collectors:
            raise ValueError(f"Collector '{collector_name}' not found or not enabled")

        collector = self.collectors[collector_name]['instance']

        logger.info(f"Running specific collector: {collector_name}")
        result = collector.collect_and_store(
            decision_context=decision_context,
            max_items=100
        )

        return result
