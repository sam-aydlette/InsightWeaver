"""
Feed loading: reads ``config/feeds/`` and nothing else.

Profile matching (``match_feeds_to_profile``, ``_calculate_match_score``,
``_get_default_preferences``, ``get_feed_statistics``, ``get_available_tags``)
left with ``src/feed_manager.py`` on 2026-09-22 (backlog task 027): there is no
profile for it to match against. What remains is the loader every adapter run
still needs.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Feed:
    """Represents a configured source with applicability metadata"""

    name: str
    url: str
    scope: list[str]  # always, global, national, regional, local
    geo_tags: list[str]  # virginia, northern_virginia, usa, etc.
    domain_tags: list[str]  # cybersecurity, technology, etc.
    specialty_tags: list[str]  # threat_intelligence, education, etc.
    relevance_score: float  # 0-1, how generally useful
    source_file: str  # which JSON file it came from
    # Which ingestion adapter reads this source (backlog task 005, 2026-08-26).
    # Defaults to "rss" so every pre-existing entry keeps its exact behaviour;
    # see src/sources/ for the adapters and SOURCES.md for the basis of use.
    adapter: str = "rss"


class FeedMatcher:
    """Loads every feed declared under ``config/feeds/`` and nothing else."""

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
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                for feed_data in data.get("feeds", []):
                    applicability = feed_data.get("applicability", {})

                    feed = Feed(
                        name=feed_data["name"],
                        url=feed_data["url"],
                        scope=applicability.get("scope", []),
                        geo_tags=applicability.get("geo_tags", []),
                        domain_tags=applicability.get("domain_tags", []),
                        specialty_tags=applicability.get("specialty_tags", []),
                        relevance_score=feed_data.get("relevance_score", 0.5),
                        source_file=str(json_file.relative_to(self.feeds_dir)),
                        adapter=feed_data.get("adapter", "rss"),
                    )
                    self.all_feeds.append(feed)

                logger.debug(f"Loaded {len(data.get('feeds', []))} feeds from {json_file.name}")

            except Exception as e:
                logger.error(f"Error loading feeds from {json_file}: {e}")

        logger.info(f"Loaded {len(self.all_feeds)} total feeds from {self.feeds_dir}")
