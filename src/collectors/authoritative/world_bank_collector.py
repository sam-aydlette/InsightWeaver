"""
World Bank Data Collector
Collects economic indicators, development data, and global statistics
for long-term trend forecasting
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

from ..base_collector import BaseCollector

logger = logging.getLogger(__name__)


class WorldBankCollector(BaseCollector):
    """
    Collects authoritative data from World Bank API

    Data includes:
    - GDP growth rates
    - Inflation indicators
    - Trade balances
    - Development indicators
    - Global economic trends

    Free API access, no key required
    API documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
    """

    # World Bank API v2 endpoints
    INDICATORS_ENDPOINT = "https://api.worldbank.org/v2/country/all/indicator"
    COUNTRY_ENDPOINT = "https://api.worldbank.org/v2/country"

    # Key indicators for forecasting
    KEY_INDICATORS = {
        'NY.GDP.MKTP.KD.ZG': 'GDP growth (annual %)',
        'FP.CPI.TOTL.ZG': 'Inflation, consumer prices (annual %)',
        'SP.POP.TOTL': 'Population, total',
        'NY.GDP.PCAP.CD': 'GDP per capita (current US$)',
        'NE.TRD.GNFS.ZS': 'Trade (% of GDP)',
        'SL.UEM.TOTL.ZS': 'Unemployment, total (% of total labor force)',
        'IT.NET.USER.ZS': 'Internet users (% of population)',
        'EN.ATM.CO2E.PC': 'CO2 emissions (metric tons per capita)'
    }

    def __init__(self):
        """Initialize World Bank collector"""
        super().__init__(
            source_name="World Bank",
            source_type="statistical_data",
            endpoint_url=self.INDICATORS_ENDPOINT,
            api_key=None  # No API key required
        )

    def fetch_data(self) -> List[Dict[str, Any]]:
        """
        Fetch data from World Bank API

        Returns:
            List of indicator data points
        """
        all_data = []

        # Fetch most recent year of data for key indicators
        for indicator_code, indicator_name in self.KEY_INDICATORS.items():
            data = self._fetch_indicator(indicator_code, indicator_name)
            all_data.extend(data)

        logger.info(f"Fetched {len(all_data)} data points from World Bank")
        return all_data

    def _fetch_indicator(self, indicator_code: str, indicator_name: str) -> List[Dict[str, Any]]:
        """
        Fetch data for a specific indicator

        Args:
            indicator_code: World Bank indicator code
            indicator_name: Human-readable indicator name

        Returns:
            List of data points for this indicator
        """
        try:
            logger.info(f"Fetching World Bank indicator: {indicator_name}")

            # Request most recent 2 years of data for major economies
            # Format: /country/{countries}/indicator/{indicator}?date={years}&format=json
            countries = "US;CN;JP;DE;GB;FR;IN;BR"  # Major economies
            url = f"{self.INDICATORS_ENDPOINT}/{indicator_code}"

            params = {
                'date': f'{datetime.now().year - 1}:{datetime.now().year}',  # Last 2 years
                'format': 'json',
                'per_page': 500
            }

            response = self.http_client.get(
                url,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()

            # World Bank returns [metadata, data]
            if len(data) < 2 or not data[1]:
                logger.warning(f"No data returned for {indicator_name}")
                return []

            results = []
            for item in data[1]:
                if item.get('value') is not None:  # Skip null values
                    item['indicator_code'] = indicator_code
                    item['indicator_name'] = indicator_name
                    item['collection_date'] = datetime.now().isoformat()
                    results.append(item)

            logger.info(f"Fetched {len(results)} values for {indicator_name}")
            return results

        except Exception as e:
            logger.error(f"Error fetching World Bank indicator {indicator_name}: {e}")
            return []

    def parse_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw World Bank data into standardized format

        Args:
            raw_item: Raw data dict from World Bank API

        Returns:
            Standardized data point dict
        """
        indicator_name = raw_item.get('indicator_name', 'Unknown Indicator')
        country_name = raw_item.get('country', {}).get('value', 'Unknown Country')
        year = raw_item.get('date', 'Unknown Year')
        value = raw_item.get('value', 'N/A')

        # Build external ID
        indicator_code = raw_item.get('indicator_code', 'unknown')
        country_code = raw_item.get('countryiso3code', 'XXX')
        external_id = f"wb_{indicator_code}_{country_code}_{year}"

        # Build title
        title = f"{indicator_name} - {country_name} ({year}): {value}"

        # Build description
        description = f"Indicator: {indicator_name}\n"
        description += f"Country: {country_name}\n"
        description += f"Year: {year}\n"
        description += f"Value: {value}\n"
        description += f"Source: World Bank Open Data\n"

        # Parse collection date
        collection_date_str = raw_item.get('collection_date')
        published_date = datetime.now()
        if collection_date_str:
            try:
                published_date = datetime.fromisoformat(collection_date_str.replace('Z', '+00:00'))
            except:
                pass

        return {
            'data_type': 'world_bank_indicator',
            'external_id': external_id,
            'title': title,
            'description': description,
            'data_payload': raw_item,
            'published_date': published_date,
            'event_date': published_date
        }

    def score_relevance(
        self,
        item: Dict[str, Any],
        decision_context: Optional[Dict] = None
    ) -> tuple[float, List[str]]:
        """
        Score World Bank data relevance for forecasting

        Economic indicators are highly valuable for long-term trends

        Args:
            item: Parsed World Bank item
            decision_context: User's decision context

        Returns:
            Tuple of (relevance_score, matching_decision_ids)
        """
        # Base relevance for World Bank data
        relevance_score = 0.65
        matching_decisions = []

        # Get indicator from payload
        payload = item.get('data_payload', {})
        indicator_name = payload.get('indicator_name', '').lower()

        # Economic indicators are most valuable
        if 'gdp' in indicator_name or 'growth' in indicator_name:
            relevance_score += 0.2
        elif 'inflation' in indicator_name or 'unemployment' in indicator_name:
            relevance_score += 0.15
        elif 'trade' in indicator_name or 'population' in indicator_name:
            relevance_score += 0.1

        # Recent data is more valuable
        year = payload.get('date')
        if year:
            try:
                year_int = int(year)
                current_year = datetime.now().year
                if year_int >= current_year - 1:
                    relevance_score += 0.15  # Very recent
                elif year_int >= current_year - 2:
                    relevance_score += 0.1  # Recent
            except:
                pass

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
