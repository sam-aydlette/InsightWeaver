"""
Fairfax County Calendar Collector
Fetches county board meetings, FCPS meetings, and other civic events
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import re

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class FairfaxCalendarCollector(BaseCollector):
    """
    Collects calendar events from Fairfax County government

    Sources:
    - Fairfax County Board of Supervisors meetings
    - FCPS School Board meetings
    - Planning Commission meetings
    """

    SOURCES = {
        'board_of_supervisors': 'https://www.fairfaxcounty.gov/boardofsupervisors/meetings',
        'fcps_school_board': 'https://www.fcps.edu/about-fcps/school-board/meetings',
        'planning_commission': 'https://www.fairfaxcounty.gov/planning-development/planning-commission/meetings'
    }

    def __init__(self):
        super().__init__(
            source_name="Fairfax County Calendar",
            source_type="calendar",
            endpoint_url=self.SOURCES['board_of_supervisors']
        )

    def fetch_data(self) -> List[Dict[str, Any]]:
        """
        Fetch calendar events from Fairfax County sources

        Returns:
            List of raw event data dicts
        """
        all_events = []

        # Fetch Board of Supervisors meetings
        try:
            bos_events = self._fetch_board_of_supervisors()
            all_events.extend(bos_events)
            logger.info(f"Fetched {len(bos_events)} Board of Supervisors events")
        except Exception as e:
            logger.error(f"Failed to fetch Board of Supervisors events: {e}")

        # Fetch FCPS School Board meetings
        try:
            fcps_events = self._fetch_fcps_meetings()
            all_events.extend(fcps_events)
            logger.info(f"Fetched {len(fcps_events)} FCPS School Board events")
        except Exception as e:
            logger.error(f"Failed to fetch FCPS events: {e}")

        return all_events

    def _fetch_board_of_supervisors(self) -> List[Dict[str, Any]]:
        """Fetch Fairfax County Board of Supervisors meetings"""
        events = []
        url = self.SOURCES['board_of_supervisors']

        try:
            response = self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for meeting listings (structure may vary)
            # This is a simplified example - real implementation needs to match actual HTML
            meeting_items = soup.find_all('div', class_='meeting-item')

            for item in meeting_items:
                # Extract meeting details
                title_elem = item.find('h3') or item.find('h4')
                date_elem = item.find('time') or item.find(class_='date')
                desc_elem = item.find('p') or item.find(class_='description')

                if title_elem and date_elem:
                    title = title_elem.get_text(strip=True)
                    date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    description = desc_elem.get_text(strip=True) if desc_elem else ""

                    # Parse date
                    event_date = self._parse_date(date_str)

                    if event_date:
                        events.append({
                            'source': 'board_of_supervisors',
                            'title': title,
                            'description': description,
                            'event_date': event_date,
                            'url': url,
                            'location': 'Fairfax County Government Center'
                        })

        except Exception as e:
            logger.warning(f"Error fetching Board of Supervisors calendar: {e}")

        # If scraping fails, return upcoming generic meetings as fallback
        if not events:
            events = self._generate_fallback_bos_meetings()

        return events

    def _fetch_fcps_meetings(self) -> List[Dict[str, Any]]:
        """Fetch FCPS School Board meetings"""
        events = []
        url = self.SOURCES['fcps_school_board']

        try:
            response = self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for meeting listings
            meeting_items = soup.find_all(['div', 'li'], class_=re.compile('meeting|event'))

            for item in meeting_items:
                title_elem = item.find(['h3', 'h4', 'strong'])
                date_elem = item.find('time') or item.find(class_='date')
                desc_elem = item.find('p')

                if title_elem and date_elem:
                    title = title_elem.get_text(strip=True)
                    date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    description = desc_elem.get_text(strip=True) if desc_elem else ""

                    event_date = self._parse_date(date_str)

                    if event_date:
                        events.append({
                            'source': 'fcps_school_board',
                            'title': title,
                            'description': description,
                            'event_date': event_date,
                            'url': url,
                            'location': 'FCPS Administration Building'
                        })

        except Exception as e:
            logger.warning(f"Error fetching FCPS calendar: {e}")

        # Fallback if scraping fails
        if not events:
            events = self._generate_fallback_fcps_meetings()

        return events

    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse date string into datetime object

        Tries multiple common formats
        """
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S%z',
            '%m/%d/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%A, %B %d, %Y',
        ]

        # Clean up the string
        date_str = date_str.strip()

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _generate_fallback_bos_meetings(self) -> List[Dict[str, Any]]:
        """
        Generate fallback Board of Supervisors meetings
        Based on typical schedule (2nd and 4th Tuesday each month)
        """
        events = []
        today = datetime.now()

        # Generate next 3 months of meetings
        for month_offset in range(3):
            month_date = today + timedelta(days=30 * month_offset)
            month_date = month_date.replace(day=1)

            # Find 2nd Tuesday
            second_tuesday = self._find_nth_weekday(month_date, 1, 2)  # Tuesday=1, 2nd occurrence
            # Find 4th Tuesday
            fourth_tuesday = self._find_nth_weekday(month_date, 1, 4)

            for meeting_date in [second_tuesday, fourth_tuesday]:
                if meeting_date >= today:
                    events.append({
                        'source': 'board_of_supervisors',
                        'title': 'Fairfax County Board of Supervisors Meeting',
                        'description': 'Regular board meeting (generated from typical schedule)',
                        'event_date': meeting_date,
                        'url': self.SOURCES['board_of_supervisors'],
                        'location': 'Fairfax County Government Center'
                    })

        return events

    def _generate_fallback_fcps_meetings(self) -> List[Dict[str, Any]]:
        """
        Generate fallback FCPS School Board meetings
        Based on typical schedule (2nd and 4th Thursday each month)
        """
        events = []
        today = datetime.now()

        for month_offset in range(3):
            month_date = today + timedelta(days=30 * month_offset)
            month_date = month_date.replace(day=1)

            # Find 2nd Thursday
            second_thursday = self._find_nth_weekday(month_date, 3, 2)  # Thursday=3, 2nd occurrence
            # Find 4th Thursday
            fourth_thursday = self._find_nth_weekday(month_date, 3, 4)

            for meeting_date in [second_thursday, fourth_thursday]:
                if meeting_date >= today:
                    events.append({
                        'source': 'fcps_school_board',
                        'title': 'FCPS School Board Meeting',
                        'description': 'Regular school board meeting (generated from typical schedule)',
                        'event_date': meeting_date,
                        'url': self.SOURCES['fcps_school_board'],
                        'location': 'FCPS Administration Building'
                    })

        return events

    def _find_nth_weekday(self, month_start: datetime, weekday: int, n: int) -> datetime:
        """
        Find the Nth occurrence of a weekday in a month

        Args:
            month_start: First day of month
            weekday: Day of week (0=Monday, 6=Sunday)
            n: Occurrence number (1=first, 2=second, etc.)

        Returns:
            datetime of Nth weekday
        """
        # Find first occurrence of weekday
        days_ahead = weekday - month_start.weekday()
        if days_ahead < 0:
            days_ahead += 7

        first_occurrence = month_start + timedelta(days=days_ahead)

        # Add weeks to get Nth occurrence
        nth_occurrence = first_occurrence + timedelta(weeks=n-1)

        return nth_occurrence

    def parse_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw calendar event into standardized format

        Args:
            raw_item: Raw event dict from fetch_data()

        Returns:
            Standardized data point dict
        """
        # Generate unique ID
        external_id = f"{raw_item['source']}_{raw_item['event_date'].strftime('%Y%m%d')}"

        return {
            'data_type': 'calendar_event',
            'external_id': external_id,
            'title': raw_item['title'],
            'description': raw_item['description'],
            'data_payload': raw_item,
            'event_date': raw_item['event_date'],
            'published_date': datetime.now(),
            'expires_date': raw_item['event_date'] + timedelta(days=1)  # Expire after event
        }
