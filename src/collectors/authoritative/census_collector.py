"""
US Census Bureau Data Collector
Collects population projections, economic indicators, housing, and migration data
for long-term trend forecasting
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from ..base_collector import BaseCollector

logger = logging.getLogger(__name__)


class CensusBureauCollector(BaseCollector):
    """
    Collects authoritative statistical data from the US Census Bureau API

    Data includes:
    - Population estimates and projections
    - Economic indicators (income, poverty, employment)
    - Housing statistics
    - Migration patterns
    - Demographic trends

    Requires CENSUS_API_KEY environment variable
    API documentation: https://www.census.gov/data/developers/data-sets.html
    """

    # API endpoints for different datasets
    POPULATION_ENDPOINT = "https://api.census.gov/data/2023/pep/population"
    ACS_ENDPOINT = "https://api.census.gov/data/2022/acs/acs5"  # American Community Survey
    ECONOMIC_ENDPOINT = "https://api.census.gov/data/timeseries/eits/resconst"  # Construction

    def __init__(self, api_key: str | None = None):
        """
        Initialize Census Bureau collector

        Args:
            api_key: Census API key (or set CENSUS_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('CENSUS_API_KEY')

        super().__init__(
            source_name="US Census Bureau",
            source_type="statistical_data",
            endpoint_url=self.POPULATION_ENDPOINT,
            api_key=self.api_key
        )

    def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch data from Census Bureau API endpoints

        Returns:
            List of statistical data points
        """
        if not self.api_key:
            logger.warning("Census API key not provided, skipping collection")
            return []

        all_data = []

        # Fetch population data
        all_data.extend(self._fetch_population_data())

        # Fetch economic indicators
        all_data.extend(self._fetch_economic_data())

        # Fetch demographic data
        all_data.extend(self._fetch_demographic_data())

        logger.info(f"Fetched {len(all_data)} data points from Census Bureau")
        return all_data

    def _fetch_population_data(self) -> list[dict[str, Any]]:
        """
        Fetch population estimates and projections

        Returns:
            List of population data points
        """
        try:
            logger.info("Fetching Census population data...")

            # Query for US state population estimates
            params = {
                'get': 'POP_2023,NAME',
                'for': 'state:*',
                'key': self.api_key
            }

            response = self.http_client.get(
                self.POPULATION_ENDPOINT,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()

            # First row is headers, skip it
            if len(data) < 2:
                return []

            headers = data[0]
            rows = data[1:]

            # Convert to list of dicts
            results = []
            for row in rows:
                item = dict(zip(headers, row))
                item['data_category'] = 'population'
                item['collection_date'] = datetime.now().isoformat()
                results.append(item)

            logger.info(f"Fetched {len(results)} population estimates")
            return results

        except Exception as e:
            logger.error(f"Error fetching population data: {e}")
            return []

    def _fetch_economic_data(self) -> list[dict[str, Any]]:
        """
        Fetch economic indicators from American Community Survey

        Returns:
            List of economic data points
        """
        try:
            logger.info("Fetching Census economic data...")

            # Query for median household income by state
            params = {
                'get': 'NAME,B19013_001E',  # Median household income
                'for': 'state:*',
                'key': self.api_key
            }

            response = self.http_client.get(
                self.ACS_ENDPOINT,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()

            if len(data) < 2:
                return []

            headers = data[0]
            rows = data[1:]

            results = []
            for row in rows:
                item = dict(zip(headers, row))
                item['data_category'] = 'economic'
                item['metric'] = 'median_household_income'
                item['collection_date'] = datetime.now().isoformat()
                results.append(item)

            logger.info(f"Fetched {len(results)} economic indicators")
            return results

        except Exception as e:
            logger.error(f"Error fetching economic data: {e}")
            return []

    def _fetch_demographic_data(self) -> list[dict[str, Any]]:
        """
        Fetch demographic trends from ACS

        Returns:
            List of demographic data points
        """
        try:
            logger.info("Fetching Census demographic data...")

            # Query for age distribution by state
            params = {
                'get': 'NAME,B01001_001E',  # Total population for age demographics
                'for': 'state:*',
                'key': self.api_key
            }

            response = self.http_client.get(
                self.ACS_ENDPOINT,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()

            if len(data) < 2:
                return []

            headers = data[0]
            rows = data[1:]

            results = []
            for row in rows:
                item = dict(zip(headers, row))
                item['data_category'] = 'demographic'
                item['metric'] = 'total_population'
                item['collection_date'] = datetime.now().isoformat()
                results.append(item)

            logger.info(f"Fetched {len(results)} demographic indicators")
            return results

        except Exception as e:
            logger.error(f"Error fetching demographic data: {e}")
            return []

    def parse_item(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """
        Parse raw Census data into standardized format

        Args:
            raw_item: Raw data dict from Census API

        Returns:
            Standardized data point dict
        """
        category = raw_item.get('data_category', 'unknown')
        geography = raw_item.get('NAME', 'Unknown Location')
        metric = raw_item.get('metric', category)

        # Build external ID
        state_code = raw_item.get('state', 'US')
        external_id = f"census_{category}_{state_code}_{datetime.now().strftime('%Y%m')}"

        # Build title
        if category == 'population':
            pop_value = raw_item.get('POP_2023', 'N/A')
            title = f"Population Estimate - {geography}: {pop_value}"
        elif category == 'economic':
            income_value = raw_item.get('B19013_001E', 'N/A')
            title = f"Median Household Income - {geography}: ${income_value}"
        elif category == 'demographic':
            pop_value = raw_item.get('B01001_001E', 'N/A')
            title = f"Total Population - {geography}: {pop_value}"
        else:
            title = f"Census Data - {geography}"

        # Build description
        description = f"Category: {category.capitalize()}\n"
        description += f"Geography: {geography}\n"
        description += "Source: US Census Bureau\n"
        description += f"Collection Date: {raw_item.get('collection_date', 'Unknown')}\n"

        # Add metric-specific details
        if category == 'economic':
            description += f"Metric: {metric}\n"

        # Parse collection date
        collection_date_str = raw_item.get('collection_date')
        published_date = datetime.now()
        if collection_date_str:
            try:
                published_date = datetime.fromisoformat(collection_date_str.replace('Z', '+00:00'))
            except:
                pass

        return {
            'data_type': 'census_statistical',
            'external_id': external_id,
            'title': title,
            'description': description,
            'data_payload': raw_item,
            'published_date': published_date,
            'event_date': published_date
        }

    def score_relevance(
        self,
        item: dict[str, Any],
        decision_context: dict | None = None
    ) -> tuple[float, list[str]]:
        """
        Score Census data relevance for forecasting

        Statistical data from Census is valuable for long-term trends,
        prioritize recent data and economic indicators.

        Args:
            item: Parsed Census item
            decision_context: User's decision context

        Returns:
            Tuple of (relevance_score, matching_decision_ids)
        """
        # Base relevance for census data
        relevance_score = 0.6
        matching_decisions = []

        # Get data category from payload
        payload = item.get('data_payload', {})
        category = payload.get('data_category', '')

        # Economic indicators are most valuable for forecasting
        if category == 'economic':
            relevance_score += 0.2

        # Population data is also highly valuable
        elif category == 'population':
            relevance_score += 0.15

        # Demographic trends are moderately valuable
        elif category == 'demographic':
            relevance_score += 0.1

        # Recent data is more valuable
        if item.get('published_date'):
            published_date = item['published_date']
            if published_date.tzinfo is not None:
                now = datetime.now(UTC)
            else:
                now = datetime.utcnow()

            days_old = (now - published_date).days
            if days_old < 30:
                relevance_score += 0.1  # Very recent
            elif days_old < 90:
                relevance_score += 0.05  # Recent

        # Check against decision context if provided
        if decision_context:
            searchable_text = f"{item.get('title', '')} {item.get('description', '')}".lower()

            for decision in decision_context.get('active_decisions', []):
                decision_id = decision.get('decision_id')
                relevant_signals = decision.get('relevant_signals', [])

                matches = sum(
                    1 for signal in relevant_signals
                    if signal.lower() in searchable_text
                )

                if matches > 0:
                    matching_decisions.append(decision_id)
                    relevance_score += min(matches * 0.1, 0.2)

        # Cap at 1.0
        relevance_score = min(relevance_score, 1.0)

        return relevance_score, matching_decisions
