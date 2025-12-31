"""
Think Tank Collector
Collects policy research and analysis from major nonpartisan think tanks
Uses RSS feeds for research publications
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import feedparser

from ..base_collector import BaseCollector

logger = logging.getLogger(__name__)


class ThinkTankCollector(BaseCollector):
    """
    Collects research and analysis from major think tanks

    Sources (nonpartisan, diverse perspectives):
    - RAND Corporation
    - Brookings Institution
    - Council on Foreign Relations (CFR)
    - Center for Strategic and International Studies (CSIS)
    - Carnegie Endowment for International Peace
    - Peterson Institute for International Economics

    Uses RSS feeds for publications
    """

    THINK_TANK_FEEDS = {
        'RAND': 'https://www.rand.org/pubs.xml',
        'Brookings': 'https://www.brookings.edu/feed/',
        'CFR': 'https://www.cfr.org/rss/feed/',
        'CSIS': 'https://www.csis.org/analysis/feed',
        'Carnegie': 'https://carnegieendowment.org/rss/publications.xml',
        'Peterson': 'https://www.piie.com/rss/research.xml'
    }

    def __init__(self):
        """Initialize Think Tank collector"""
        super().__init__(
            source_name="Think Tanks",
            source_type="research",
            endpoint_url="multiple_rss_feeds",
            api_key=None
        )

    def fetch_data(self) -> List[Dict[str, Any]]:
        """
        Fetch research publications from think tank RSS feeds

        Returns:
            List of think tank publications
        """
        all_data = []

        for tank_name, feed_url in self.THINK_TANK_FEEDS.items():
            try:
                logger.info(f"Fetching {tank_name} publications...")

                feed = feedparser.parse(feed_url)

                # Get recent publications (last 30 days)
                cutoff = datetime.now() - timedelta(days=30)

                for entry in feed.entries[:20]:  # Limit to 20 most recent
                    # Parse publication date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            pub_date = datetime(*entry.published_parsed[:6])
                        except:
                            pass

                    # Skip if too old
                    if pub_date and pub_date < cutoff:
                        continue

                    # Build data item
                    item = {
                        'think_tank': tank_name,
                        'title': entry.get('title', 'Untitled'),
                        'link': entry.get('link', ''),
                        'summary': entry.get('summary', ''),
                        'published': pub_date.isoformat() if pub_date else datetime.now().isoformat(),
                        'collection_date': datetime.now().isoformat()
                    }

                    all_data.append(item)

                logger.info(f"Fetched {len([d for d in all_data if d['think_tank'] == tank_name])} publications from {tank_name}")

            except Exception as e:
                logger.error(f"Error fetching {tank_name} feed: {e}")
                continue

        logger.info(f"Fetched {len(all_data)} total think tank publications")
        return all_data

    def parse_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw think tank publication into standardized format

        Args:
            raw_item: Raw publication dict from RSS feed

        Returns:
            Standardized data point dict
        """
        tank_name = raw_item.get('think_tank', 'Unknown')
        title = raw_item.get('title', 'Untitled')
        summary = raw_item.get('summary', '')
        link = raw_item.get('link', '')

        # Build external ID
        external_id = f"think_tank_{tank_name}_{hash(link)}"

        # Build title with source
        full_title = f"[{tank_name}] {title}"

        # Build description
        description = f"Think Tank: {tank_name}\n"
        description += f"Title: {title}\n"
        if summary:
            description += f"Summary: {summary[:500]}...\n"
        description += f"URL: {link}\n"
        description += f"Source Type: Policy Research\n"

        # Parse published date
        published_str = raw_item.get('published')
        published_date = datetime.now()
        if published_str:
            try:
                published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            except:
                pass

        return {
            'data_type': 'think_tank_research',
            'external_id': external_id,
            'title': full_title,
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
        Score think tank research relevance for forecasting

        Policy research is highly valuable for long-term trends

        Args:
            item: Parsed think tank item
            decision_context: User's decision context

        Returns:
            Tuple of (relevance_score, matching_decision_ids)
        """
        # Base relevance for think tank research
        relevance_score = 0.7  # Higher than news, policy research is authoritative
        matching_decisions = []

        # Recent publications are more valuable
        if item.get('published_date'):
            published_date = item['published_date']
            if published_date.tzinfo is not None:
                from datetime import timezone
                now = datetime.now(timezone.utc)
            else:
                now = datetime.utcnow()

            days_old = (now - published_date).days
            if days_old < 7:
                relevance_score += 0.15  # Very recent
            elif days_old < 30:
                relevance_score += 0.1  # Recent

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
