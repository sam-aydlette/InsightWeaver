"""
Feed Matcher - Tag-based Feed Selection System
Matches RSS feeds to user profiles based on applicability tags
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Feed:
    """Represents an RSS feed with applicability metadata"""
    name: str
    url: str
    scope: list[str]  # always, global, national, regional, local
    geo_tags: list[str]  # virginia, northern_virginia, usa, etc.
    domain_tags: list[str]  # cybersecurity, technology, etc.
    specialty_tags: list[str]  # threat_intelligence, education, etc.
    relevance_score: float  # 0-1, how generally useful
    source_file: str  # which JSON file it came from


class FeedMatcher:
    """Matches feeds to user profiles based on tag-based applicability"""

    def __init__(self, feeds_directory: str = "config/feeds"):
        """
        Initialize feed matcher

        Args:
            feeds_directory: Path to feeds directory structure
        """
        self.feeds_dir = Path(feeds_directory)
        self.all_feeds: list[Feed] = []
        self._load_all_feeds()

    def _load_all_feeds(self) -> None:
        """Load all feeds from JSON files in the feeds directory"""
        if not self.feeds_dir.exists():
            logger.error(f"Feeds directory not found: {self.feeds_dir}")
            return

        # Load feeds from all JSON files recursively
        for json_file in self.feeds_dir.rglob("*.json"):
            try:
                with open(json_file, encoding='utf-8') as f:
                    data = json.load(f)

                for feed_data in data.get('feeds', []):
                    applicability = feed_data.get('applicability', {})

                    feed = Feed(
                        name=feed_data['name'],
                        url=feed_data['url'],
                        scope=applicability.get('scope', []),
                        geo_tags=applicability.get('geo_tags', []),
                        domain_tags=applicability.get('domain_tags', []),
                        specialty_tags=applicability.get('specialty_tags', []),
                        relevance_score=feed_data.get('relevance_score', 0.5),
                        source_file=str(json_file.relative_to(self.feeds_dir))
                    )
                    self.all_feeds.append(feed)

                logger.debug(f"Loaded {len(data.get('feeds', []))} feeds from {json_file.name}")

            except Exception as e:
                logger.error(f"Error loading feeds from {json_file}: {e}")

        logger.info(f"Loaded {len(self.all_feeds)} total feeds from {self.feeds_dir}")

    def match_feeds_to_profile(self, user_profile) -> list[dict[str, Any]]:
        """
        Match feeds to user profile based on tags

        Args:
            user_profile: UserProfile instance with feed preferences

        Returns:
            List of feed dictionaries sorted by relevance
        """
        try:
            prefs = user_profile.profile.get('feed_preferences', {})
        except AttributeError:
            logger.warning("User profile has no feed_preferences, using defaults")
            prefs = self._get_default_preferences()

        matched_feeds = []

        for feed in self.all_feeds:
            score = self._calculate_match_score(feed, prefs)

            if score > 0:
                matched_feeds.append({
                    'name': feed.name,
                    'url': feed.url,
                    'category': feed.domain_tags[0] if feed.domain_tags else 'uncategorized',
                    'match_score': score,
                    'source_file': feed.source_file
                })

        # Sort by match score (highest first)
        matched_feeds.sort(key=lambda x: x['match_score'], reverse=True)

        logger.info(f"Matched {len(matched_feeds)} feeds to user profile")
        return matched_feeds

    def _calculate_match_score(self, feed: Feed, preferences: dict[str, Any]) -> float:
        """
        Calculate match score for a feed based on user preferences

        Scoring:
        - Scope match (required_scopes): +10 points
        - Geographic match: +5 points
        - Professional domain match: +3 points
        - Specialty interest match: +2 points
        - Base relevance_score: +0-10 points
        - Excluded topics: 0 points (hard exclude)

        Args:
            feed: Feed to score
            preferences: User feed preferences

        Returns:
            Match score (0 = no match, higher = better match)
        """
        score = 0.0

        # Get preference lists
        required_scopes = preferences.get('required_scopes', ['always', 'national'])
        geo_interests = preferences.get('geographic_interests', [])
        prof_domains = preferences.get('professional_domains', [])
        specialty_interests = preferences.get('specialty_interests', [])
        excluded_topics = preferences.get('excluded_topics', [])

        # 1. Check for exclusions (hard stop)
        for excluded in excluded_topics:
            if (excluded in feed.domain_tags or
                excluded in feed.specialty_tags or
                excluded in feed.geo_tags):
                return 0.0

        # 2. Scope matching (most important)
        if any(scope in feed.scope for scope in required_scopes):
            score += 10.0

        # 3. Geographic matching
        if any(geo in feed.geo_tags for geo in geo_interests):
            score += 5.0

        # 4. Professional domain matching
        if any(domain in feed.domain_tags for domain in prof_domains):
            score += 3.0

        # 5. Specialty interest matching
        if any(spec in feed.specialty_tags for spec in specialty_interests):
            score += 2.0

        # 6. Add base relevance score (0-10 scale)
        score += feed.relevance_score * 10

        return score

    def _get_default_preferences(self) -> dict[str, Any]:
        """Get default feed preferences for users without configuration"""
        return {
            'required_scopes': ['always', 'national'],
            'geographic_interests': ['usa'],
            'professional_domains': [],
            'specialty_interests': [],
            'excluded_topics': []
        }

    def get_feed_statistics(self) -> dict[str, Any]:
        """Get statistics about loaded feeds"""
        stats = {
            'total_feeds': len(self.all_feeds),
            'by_scope': {},
            'by_geo': {},
            'by_domain': {},
            'by_source_file': {}
        }

        for feed in self.all_feeds:
            # Count by scope
            for scope in feed.scope:
                stats['by_scope'][scope] = stats['by_scope'].get(scope, 0) + 1

            # Count by geography
            for geo in feed.geo_tags:
                stats['by_geo'][geo] = stats['by_geo'].get(geo, 0) + 1

            # Count by domain
            for domain in feed.domain_tags:
                stats['by_domain'][domain] = stats['by_domain'].get(domain, 0) + 1

            # Count by source file
            stats['by_source_file'][feed.source_file] = stats['by_source_file'].get(feed.source_file, 0) + 1

        return stats

    def get_available_tags(self) -> dict[str, list[str]]:
        """Get all available tags for user reference"""
        scopes = set()
        geo_tags = set()
        domain_tags = set()
        specialty_tags = set()

        for feed in self.all_feeds:
            scopes.update(feed.scope)
            geo_tags.update(feed.geo_tags)
            domain_tags.update(feed.domain_tags)
            specialty_tags.update(feed.specialty_tags)

        return {
            'scopes': sorted(list(scopes)),
            'geographic_tags': sorted(list(geo_tags)),
            'domain_tags': sorted(list(domain_tags)),
            'specialty_tags': sorted(list(specialty_tags))
        }
