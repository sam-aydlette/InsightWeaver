"""
Event Monitor Collector
Tracks concert tours and live music events for specified artists
"""

import logging
from datetime import datetime
from typing import Any

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class EventMonitorCollector(BaseCollector):
    """
    Monitors concert and event announcements for specified artists

    Uses Bandsintown API (free tier available)
    Alternative: Songkick API, Ticketmaster API
    """

    BANDSINTOWN_API_URL = "https://rest.bandsintown.com/artists/{artist}/events"

    def __init__(self, artists: list[str], app_id: str = "insightweaver"):
        """
        Initialize event monitor

        Args:
            artists: List of artist names to monitor
            app_id: App identifier for Bandsintown API
        """
        super().__init__(
            source_name="Bandsintown Events",
            source_type="events",
            endpoint_url=self.BANDSINTOWN_API_URL
        )
        self.artists = artists
        self.app_id = app_id

    def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch upcoming events for configured artists

        Returns:
            List of raw event data dicts
        """
        all_events = []

        for artist in self.artists:
            try:
                events = self._fetch_artist_events(artist)
                all_events.extend(events)
                logger.info(f"Fetched {len(events)} events for {artist}")
            except Exception as e:
                logger.error(f"Failed to fetch events for {artist}: {e}")

        return all_events

    def _fetch_artist_events(self, artist: str) -> list[dict[str, Any]]:
        """
        Fetch events for a specific artist from Bandsintown

        Args:
            artist: Artist name

        Returns:
            List of event dicts
        """
        # Clean artist name for URL
        artist_encoded = artist.replace(' ', '%20')
        url = self.BANDSINTOWN_API_URL.format(artist=artist_encoded)

        params = {
            'app_id': self.app_id,
            'date': 'upcoming'  # Only upcoming events
        }

        try:
            response = self.http_client.get(url, params=params)
            response.raise_for_status()

            events_data = response.json()

            # Handle case where API returns empty list or error
            if not events_data or not isinstance(events_data, list):
                logger.warning(f"No events found for {artist}")
                return []

            # Filter for DC/NoVA area events
            filtered_events = []
            for event in events_data:
                if self._is_local_event(event):
                    # Add artist name to event data
                    event['artist_name'] = artist
                    filtered_events.append(event)

            logger.info(f"Found {len(filtered_events)} local events for {artist}")
            return filtered_events

        except Exception as e:
            logger.error(f"Error fetching Bandsintown events for {artist}: {e}")
            return []

    def _is_local_event(self, event: dict[str, Any]) -> bool:
        """
        Check if event is in DC/Northern Virginia area

        Args:
            event: Event data from Bandsintown API

        Returns:
            True if event is local
        """
        venue = event.get('venue', {})
        city = venue.get('city', '').lower()
        region = venue.get('region', '').lower()
        country = venue.get('country', '').lower()

        # Only US events
        if country not in ['us', 'united states']:
            return False

        # DC/NoVA cities
        local_cities = [
            'washington', 'arlington', 'alexandria', 'fairfax',
            'falls church', 'mclean', 'tysons', 'vienna',
            'reston', 'herndon', 'sterling', 'leesburg',
            'manassas', 'fredericksburg', 'baltimore'  # Include nearby metro areas
        ]

        # Virginia, DC, or Maryland
        local_regions = ['va', 'virginia', 'dc', 'district of columbia', 'md', 'maryland']

        # Check if city or region matches
        for local_city in local_cities:
            if local_city in city:
                return True

        for local_region in local_regions:
            if local_region in region:
                return True

        return False

    def parse_item(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """
        Parse raw event into standardized format

        Args:
            raw_item: Raw event dict from Bandsintown API

        Returns:
            Standardized data point dict
        """
        # Extract event details
        artist = raw_item.get('artist_name', 'Unknown Artist')
        venue = raw_item.get('venue', {})
        venue_name = venue.get('name', 'Unknown Venue')
        city = venue.get('city', '')
        region = venue.get('region', '')

        # Parse datetime
        datetime_str = raw_item.get('datetime', '')
        try:
            event_date = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except:
            event_date = None

        # Build title and description
        title = f"{artist} at {venue_name}"
        location_str = f"{city}, {region}".strip(', ')
        description = f"Concert: {artist}\nVenue: {venue_name}\nLocation: {location_str}"

        # Add lineup if available
        lineup = raw_item.get('lineup', [])
        if lineup and len(lineup) > 1:
            description += f"\nLineup: {', '.join(lineup)}"

        # Generate unique ID
        external_id = raw_item.get('id', f"{artist}_{datetime_str}")

        return {
            'data_type': 'concert_event',
            'external_id': str(external_id),
            'title': title,
            'description': description,
            'data_payload': raw_item,
            'event_date': event_date,
            'published_date': datetime.now(),
            'expires_date': event_date if event_date else None
        }


class SongkickCollector(BaseCollector):
    """
    Alternative collector using Songkick API
    Requires API key from https://www.songkick.com/developer
    """

    SONGKICK_API_URL = "https://api.songkick.com/api/3.0/artists/{artist_id}/calendar.json"

    def __init__(self, api_key: str, artist_ids: dict[str, int]):
        """
        Initialize Songkick collector

        Args:
            api_key: Songkick API key
            artist_ids: Dict mapping artist names to Songkick artist IDs
        """
        super().__init__(
            source_name="Songkick Events",
            source_type="events",
            endpoint_url=self.SONGKICK_API_URL,
            api_key=api_key
        )
        self.artist_ids = artist_ids

    def fetch_data(self) -> list[dict[str, Any]]:
        """Fetch events from Songkick"""
        all_events = []

        for artist_name, artist_id in self.artist_ids.items():
            try:
                url = self.SONGKICK_API_URL.format(artist_id=artist_id)
                params = {'apikey': self.api_key}

                response = self.http_client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                events = data.get('resultsPage', {}).get('results', {}).get('event', [])

                # Add artist name and filter for local events
                for event in events:
                    event['artist_name'] = artist_name
                    if self._is_local_songkick_event(event):
                        all_events.append(event)

                logger.info(f"Fetched {len(events)} events for {artist_name} from Songkick")

            except Exception as e:
                logger.error(f"Failed to fetch Songkick events for {artist_name}: {e}")

        return all_events

    def _is_local_songkick_event(self, event: dict[str, Any]) -> bool:
        """Check if Songkick event is in DC/NoVA area"""
        venue = event.get('venue', {})
        location = venue.get('metroArea', {})
        city = location.get('displayName', '').lower()
        state = location.get('state', {}).get('displayName', '').lower()

        local_metros = ['washington', 'baltimore']
        local_states = ['virginia', 'maryland', 'dc']

        return any(metro in city for metro in local_metros) or \
               any(st in state for st in local_states)

    def parse_item(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Parse Songkick event into standardized format"""
        artist = raw_item.get('artist_name', 'Unknown Artist')
        venue = raw_item.get('venue', {})
        venue_name = venue.get('displayName', 'Unknown Venue')

        # Parse date
        start = raw_item.get('start', {})
        date_str = start.get('datetime') or start.get('date')
        event_date = None
        if date_str:
            try:
                event_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass

        title = f"{artist} at {venue_name}"
        description = f"Concert: {artist}\nVenue: {venue_name}"

        external_id = str(raw_item.get('id', f"{artist}_{date_str}"))

        return {
            'data_type': 'concert_event',
            'external_id': external_id,
            'title': title,
            'description': description,
            'data_payload': raw_item,
            'event_date': event_date,
            'published_date': datetime.now(),
            'expires_date': event_date if event_date else None
        }
