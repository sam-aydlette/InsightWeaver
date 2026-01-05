"""
Job Market Collector
Monitors job postings relevant to user's career decisions
"""

import logging
import os
from datetime import datetime
from typing import Any

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class JobMarketCollector(BaseCollector):
    """
    Monitors job market for positions matching user's career interests

    Sources:
    - USAJobs API (federal positions)
    - GitHub Jobs (tech positions) - Note: Deprecated, but kept for reference
    - Indeed API (requires partnership)
    - LinkedIn API (requires auth)

    Primary implementation: USAJobs (free, no auth required)
    """

    USAJOBS_API_URL = "https://data.usajobs.gov/api/search"

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
        keywords: list[str] | None = None,
        location_codes: list[str] | None = None
    ):
        """
        Initialize job market collector

        Args:
            api_key: USAJobs API key (get from https://developer.usajobs.gov/)
            email: Email for USAJobs API requests
            keywords: Job search keywords
            location_codes: Location codes (e.g., 'Virginia', 'Washington DC')
        """
        # Get API key from env if not provided
        if not api_key:
            api_key = os.getenv('USAJOBS_API_KEY')

        if not email:
            email = os.getenv('USAJOBS_EMAIL', 'noreply@example.com')

        super().__init__(
            source_name="USAJobs Federal Positions",
            source_type="job_market",
            endpoint_url=self.USAJOBS_API_URL,
            api_key=api_key
        )

        self.email = email
        self.keywords = keywords or ['cybersecurity', 'information security', 'software engineer']
        self.location_codes = location_codes or ['Virginia']

    def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch job postings from USAJobs

        Returns:
            List of raw job posting dicts
        """
        all_jobs = []

        for keyword in self.keywords:
            try:
                jobs = self._fetch_usajobs(keyword)
                all_jobs.extend(jobs)
                logger.info(f"Fetched {len(jobs)} jobs for keyword: {keyword}")
            except Exception as e:
                logger.error(f"Failed to fetch jobs for {keyword}: {e}")

        # Deduplicate by job ID
        seen_ids = set()
        unique_jobs = []
        for job in all_jobs:
            job_id = job.get('MatchedObjectId')
            if job_id and job_id not in seen_ids:
                seen_ids.add(job_id)
                unique_jobs.append(job)

        logger.info(f"Total unique jobs after deduplication: {len(unique_jobs)}")
        return unique_jobs

    def _fetch_usajobs(self, keyword: str) -> list[dict[str, Any]]:
        """
        Fetch jobs from USAJobs API

        Args:
            keyword: Search keyword

        Returns:
            List of job dicts
        """
        if not self.api_key:
            logger.warning("USAJobs API key not configured, skipping federal job search")
            return []

        headers = {
            'Host': 'data.usajobs.gov',
            'User-Agent': self.email,
            'Authorization-Key': self.api_key
        }

        params = {
            'Keyword': keyword,
            'ResultsPerPage': 50,
            'Fields': 'min',  # Minimal fields to reduce response size
            'WhoMayApply': 'Public',  # Open to public
            'DatePosted': 30  # Last 30 days
        }

        # Add location filter if specified
        if self.location_codes:
            params['LocationName'] = ';'.join(self.location_codes)

        try:
            response = self.http_client.get(
                self.USAJOBS_API_URL,
                headers=headers,
                params=params
            )
            response.raise_for_status()

            data = response.json()
            search_result = data.get('SearchResult', {})
            jobs = search_result.get('SearchResultItems', [])

            logger.info(f"USAJobs API returned {len(jobs)} results for '{keyword}'")
            return jobs

        except Exception as e:
            logger.error(f"Error fetching USAJobs for '{keyword}': {e}")
            return []

    def parse_item(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """
        Parse raw job posting into standardized format

        Args:
            raw_item: Raw job dict from USAJobs API

        Returns:
            Standardized data point dict
        """
        # USAJobs has nested structure
        matched_object = raw_item.get('MatchedObjectDescriptor', {})

        # Extract key fields
        job_id = raw_item.get('MatchedObjectId', '')
        title = matched_object.get('PositionTitle', 'Unknown Position')
        organization = matched_object.get('OrganizationName', 'Unknown Agency')

        # Salary range
        salary_min = matched_object.get('PositionRemuneration', [{}])[0].get('MinimumRange', 'N/A')
        salary_max = matched_object.get('PositionRemuneration', [{}])[0].get('MaximumRange', 'N/A')
        salary_str = f"${salary_min} - ${salary_max}" if salary_min != 'N/A' else 'Salary not specified'

        # Location
        locations = matched_object.get('PositionLocationDisplay', 'Location not specified')

        # Build description
        qualifications = matched_object.get('QualificationSummary', '')
        description = f"""
Organization: {organization}
Location: {locations}
Salary: {salary_str}

Qualifications:
{qualifications[:500]}...
        """.strip()

        # Dates
        published_date_str = matched_object.get('PublicationStartDate', '')
        end_date_str = matched_object.get('ApplicationCloseDate', '')

        published_date = None
        expires_date = None

        if published_date_str:
            try:
                published_date = datetime.fromisoformat(published_date_str.replace('Z', '+00:00'))
            except:
                pass

        if end_date_str:
            try:
                expires_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except:
                pass

        # URL
        url = matched_object.get('PositionURI', '')

        return {
            'data_type': 'job_posting',
            'external_id': job_id,
            'title': f"{title} - {organization}",
            'description': description,
            'data_payload': {
                **matched_object,
                'url': url,
                'salary_range': salary_str
            },
            'event_date': None,  # Jobs don't have event dates
            'published_date': published_date,
            'expires_date': expires_date
        }


class ClearedJobsCollector(BaseCollector):
    """
    Collector for ClearedJobs.net (security clearance required positions)
    Note: No official API - would require web scraping
    """

    CLEARANCE_JOBS_URL = "https://www.clearancejobs.com/jobs"

    def __init__(self, keywords: list[str], location: str = "Virginia"):
        super().__init__(
            source_name="ClearedJobs Scraper",
            source_type="job_market",
            endpoint_url=self.CLEARANCE_JOBS_URL
        )
        self.keywords = keywords
        self.location = location

    def fetch_data(self) -> list[dict[str, Any]]:
        """
        Scrape job listings from ClearedJobs.net

        Note: This is a placeholder. Real implementation would use
        BeautifulSoup to parse job listings from search results.
        """
        logger.warning("ClearedJobs scraping not yet implemented - requires HTML parsing")
        return []

    def parse_item(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Parse scraped job posting"""
        return {
            'data_type': 'job_posting',
            'external_id': raw_item.get('id', ''),
            'title': raw_item.get('title', ''),
            'description': raw_item.get('description', ''),
            'data_payload': raw_item,
            'event_date': None,
            'published_date': raw_item.get('published_date'),
            'expires_date': None
        }
