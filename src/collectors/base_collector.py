"""
Base collector class for API and structured data sources
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import APIDataPoint, APIDataSource

logger = logging.getLogger(__name__)


class CollectorError(Exception):
    """Base exception for collector errors"""
    pass


class BaseCollector(ABC):
    """
    Abstract base class for data collectors

    Collectors fetch data from APIs and structured sources,
    score relevance against user decisions, and store results
    """

    def __init__(
        self,
        source_name: str,
        source_type: str,
        endpoint_url: str | None = None,
        api_key: str | None = None
    ):
        """
        Initialize collector

        Args:
            source_name: Human-readable name for this source
            source_type: Type category ('calendar', 'job_market', 'events', etc.)
            endpoint_url: API endpoint URL
            api_key: API key if required
        """
        self.source_name = source_name
        self.source_type = source_type
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.http_client = httpx.Client(timeout=30.0, follow_redirects=True)

    def __del__(self):
        """Cleanup HTTP client"""
        if hasattr(self, 'http_client'):
            self.http_client.close()

    @staticmethod
    def _serialize_for_json(obj: Any) -> Any:
        """
        Recursively serialize objects for JSON storage
        Converts datetime objects to ISO format strings
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: BaseCollector._serialize_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [BaseCollector._serialize_for_json(item) for item in obj]
        else:
            return obj

    def _get_or_create_source(self, session: Session) -> APIDataSource:
        """Get or create the APIDataSource record for this collector"""
        source = session.query(APIDataSource).filter(
            APIDataSource.name == self.source_name
        ).first()

        if not source:
            source = APIDataSource(
                name=self.source_name,
                source_type=self.source_type,
                endpoint_url=self.endpoint_url,
                api_key_required=self.api_key is not None,
                is_active=True
            )
            session.add(source)
            session.commit()
            logger.info(f"Created new API data source: {self.source_name}")

        return source

    @abstractmethod
    def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch data from the source

        Returns:
            List of data items (dicts with standardized fields)
        """
        pass

    @abstractmethod
    def parse_item(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """
        Parse a raw data item into standardized format

        Args:
            raw_item: Raw data from API

        Returns:
            Standardized dict with keys:
                - data_type: str ('event', 'job_posting', etc.)
                - external_id: str (unique ID from source)
                - title: str
                - description: str
                - data_payload: dict (full raw data)
                - event_date: datetime (optional)
                - published_date: datetime (optional)
                - expires_date: datetime (optional)
        """
        pass

    def score_relevance(
        self,
        item: dict[str, Any],
        decision_context: dict | None = None
    ) -> tuple[float, list[str]]:
        """
        Score item relevance against user's active decisions

        Args:
            item: Parsed data item
            decision_context: User's decision context (from decision_context.json)

        Returns:
            Tuple of (relevance_score: float, matching_decision_ids: List[str])
        """
        if not decision_context:
            return 0.5, []  # Neutral score if no decision context

        matching_decisions = []
        relevance_score = 0.0

        # Get searchable text from item
        searchable_text = f"{item.get('title', '')} {item.get('description', '')}".lower()

        # Check against each active decision
        for decision in decision_context.get('active_decisions', []):
            decision_id = decision.get('decision_id')
            relevant_signals = decision.get('relevant_signals', [])

            # Count keyword matches
            matches = sum(
                1 for signal in relevant_signals
                if signal.lower() in searchable_text
            )

            if matches > 0:
                matching_decisions.append(decision_id)
                # Score increases with number of matching signals
                relevance_score += min(matches * 0.3, 1.0)

        # Cap at 1.0 and ensure minimum of 0.1 if any matches
        if relevance_score > 0:
            relevance_score = min(relevance_score, 1.0)
        else:
            relevance_score = 0.1  # Base score for items that don't match

        return relevance_score, matching_decisions

    def collect_and_store(
        self,
        decision_context: dict | None = None,
        max_items: int = 100
    ) -> dict[str, Any]:
        """
        Main collection method: fetch, parse, score, and store data

        Args:
            decision_context: User's decision context for relevance scoring
            max_items: Maximum items to process

        Returns:
            Collection stats dict
        """
        with get_db() as session:
            source = self._get_or_create_source(session)

            try:
                logger.info(f"Fetching data from {self.source_name}")
                raw_items = self.fetch_data()
                logger.info(f"Fetched {len(raw_items)} items from {self.source_name}")

                new_items = 0
                updated_items = 0
                skipped_items = 0

                for raw_item in raw_items[:max_items]:
                    try:
                        # Parse item
                        parsed = self.parse_item(raw_item)

                        # Score relevance
                        relevance_score, decision_ids = self.score_relevance(
                            parsed, decision_context
                        )

                        # Check if item already exists
                        existing = session.query(APIDataPoint).filter(
                            APIDataPoint.source_id == source.id,
                            APIDataPoint.external_id == parsed['external_id']
                        ).first()

                        if existing:
                            # Update relevance score if changed
                            if existing.relevance_score != relevance_score:
                                existing.relevance_score = relevance_score
                                existing.decision_ids = decision_ids
                                updated_items += 1
                            else:
                                skipped_items += 1
                        else:
                            # Create new data point
                            # Serialize data_payload to ensure all datetime objects are converted
                            serialized_payload = self._serialize_for_json(parsed['data_payload'])

                            data_point = APIDataPoint(
                                source_id=source.id,
                                data_type=parsed['data_type'],
                                external_id=parsed['external_id'],
                                title=parsed.get('title'),
                                description=parsed.get('description'),
                                data_payload=serialized_payload,
                                event_date=parsed.get('event_date'),
                                published_date=parsed.get('published_date'),
                                expires_date=parsed.get('expires_date'),
                                relevance_score=relevance_score,
                                decision_ids=decision_ids
                            )
                            session.add(data_point)
                            new_items += 1

                    except Exception as e:
                        logger.error(f"Error processing item from {self.source_name}: {e}")
                        continue

                # Update source status
                source.last_fetched = datetime.utcnow()
                source.error_count = 0
                source.last_error = None
                session.commit()

                stats = {
                    'source': self.source_name,
                    'total_fetched': len(raw_items),
                    'new_items': new_items,
                    'updated_items': updated_items,
                    'skipped_items': skipped_items,
                    'success': True
                }

                logger.info(f"Collection complete: {stats}")
                return stats

            except Exception as e:
                # Update source error status
                source.last_fetched = datetime.utcnow()
                source.error_count += 1
                source.last_error = str(e)
                session.commit()

                logger.error(f"Collection failed for {self.source_name}: {e}")
                raise CollectorError(f"Failed to collect from {self.source_name}: {e}")
