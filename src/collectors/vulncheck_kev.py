"""
VulnCheck KEV Collector
Collects Known Exploited Vulnerabilities from VulnCheck's free community API
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class VulnCheckKEVCollector(BaseCollector):
    """
    Collects Known Exploited Vulnerabilities from VulnCheck KEV

    VulnCheck KEV tracks ~3,700 vulnerabilities (175% more than CISA KEV)
    with additional context like exploit links and threat actor associations.

    Free API access available at https://vulncheck.com/
    """

    VULNCHECK_KEV_URL = "https://api.vulncheck.com/v3/backup/vulncheck-kev"

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize VulnCheck KEV collector

        Args:
            api_token: VulnCheck API token (or set VULNCHECK_API_TOKEN env var)
        """
        self.api_token = api_token or os.getenv('VULNCHECK_API_TOKEN')

        super().__init__(
            source_name="VulnCheck KEV",
            source_type="vulnerability",
            endpoint_url=self.VULNCHECK_KEV_URL,
            api_key=self.api_token
        )

    def fetch_data(self) -> List[Dict[str, Any]]:
        """
        Fetch KEV data from VulnCheck API

        Returns:
            List of vulnerability dicts
        """
        if not self.api_token:
            logger.error("VulnCheck API token not provided")
            return []

        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json'
        }

        try:
            logger.info("Fetching VulnCheck KEV data...")
            response = self.http_client.get(
                self.VULNCHECK_KEV_URL,
                headers=headers,
                timeout=60.0  # KEV data can be large
            )
            response.raise_for_status()

            data = response.json()

            # VulnCheck KEV returns data in 'data' field
            vulnerabilities = data.get('data', [])

            logger.info(f"Fetched {len(vulnerabilities)} KEV entries from VulnCheck")
            return vulnerabilities

        except Exception as e:
            logger.error(f"Error fetching VulnCheck KEV data: {e}")
            return []

    def parse_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw KEV entry into standardized format

        Args:
            raw_item: Raw vulnerability dict from VulnCheck API

        Returns:
            Standardized data point dict
        """
        # Extract core fields
        cve_list = raw_item.get('cve', [])
        cve_id = cve_list[0] if cve_list else 'UNKNOWN'

        vendor = raw_item.get('vendorProject', 'Unknown Vendor')
        product = raw_item.get('product', 'Unknown Product')
        vuln_name = raw_item.get('vulnerabilityName', '')
        short_desc = raw_item.get('shortDescription', '')

        # Build title
        if vuln_name:
            title = f"{cve_id}: {vuln_name}"
        else:
            title = f"{cve_id}: {vendor} {product}"

        # Build description
        description = f"Vendor: {vendor}\n"
        description += f"Product: {product}\n"
        if vuln_name:
            description += f"Vulnerability: {vuln_name}\n"
        description += f"\n{short_desc}\n"

        # Add exploit info if available
        xdb_exploits = raw_item.get('vulncheck_xdb', [])
        if xdb_exploits:
            description += f"\nExploits Available: {len(xdb_exploits)}"

        # Add ransomware campaign info
        ransomware = raw_item.get('knownRansomwareCampaignUse', '')
        if ransomware and ransomware.lower() not in ['unknown', 'no']:
            description += f"\nRansomware Campaign Use: {ransomware}"

        # Add required action
        required_action = raw_item.get('required_action', '')
        if required_action:
            description += f"\nRequired Action: {required_action}"

        # Parse dates
        date_added_str = raw_item.get('date_added', '')
        date_added = None
        if date_added_str:
            try:
                date_added = datetime.fromisoformat(date_added_str.replace('Z', '+00:00'))
            except:
                pass

        due_date_str = raw_item.get('dueDate', '')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            except:
                pass

        # Use CVE ID as external ID
        external_id = cve_id

        return {
            'data_type': 'vulnerability_kev',
            'external_id': external_id,
            'title': title,
            'description': description,
            'data_payload': raw_item,
            'event_date': date_added,
            'published_date': date_added,
            'expires_date': due_date  # Due date for remediation
        }

    def score_relevance(
        self,
        item: Dict[str, Any],
        decision_context: Optional[Dict] = None
    ) -> tuple[float, List[str]]:
        """
        Score KEV relevance - cybersecurity vulnerabilities are always relevant
        but prioritize based on recency and exploit availability

        Args:
            item: Parsed KEV item
            decision_context: User's decision context

        Returns:
            Tuple of (relevance_score, matching_decision_ids)
        """
        # Base relevance for all KEVs
        relevance_score = 0.7
        matching_decisions = []

        # Boost for recently added vulnerabilities (last 30 days)
        if item.get('event_date'):
            event_date = item['event_date']
            # Ensure both datetimes are timezone-aware or both are naive
            if event_date.tzinfo is not None:
                from datetime import timezone
                now = datetime.now(timezone.utc)
            else:
                now = datetime.utcnow()

            days_old = (now - event_date).days
            if days_old < 7:
                relevance_score += 0.3  # Very recent
            elif days_old < 30:
                relevance_score += 0.2  # Recent

        # Boost if exploits are available
        payload = item.get('data_payload', {})
        if payload.get('vulncheck_xdb'):
            relevance_score += 0.1

        # Boost for ransomware campaigns
        ransomware = payload.get('knownRansomwareCampaignUse', '')
        if ransomware and ransomware.lower() not in ['unknown', 'no']:
            relevance_score += 0.15

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
