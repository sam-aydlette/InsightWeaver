"""
Authoritative Source Matcher
Matches claims to authoritative web sources for temporal verification
"""

import logging
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class AuthoritativeSourceMatcher:
    """
    Matches factual claims to authoritative sources for verification
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize source matcher

        Args:
            config_path: Path to authoritative_sources.yaml (defaults to same directory)
        """
        if config_path is None:
            config_path = Path(__file__).parent / "authoritative_sources.yaml"

        self.config_path = config_path
        self.sources = []
        self.fallback_config = {}
        self._load_sources()

    def _load_sources(self):
        """Load authoritative sources from YAML config"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            self.sources = config.get('sources', [])
            self.fallback_config = config.get('fallback', {})

            logger.info(f"Loaded {len(self.sources)} authoritative sources from config")

        except FileNotFoundError:
            logger.warning(f"Authoritative sources config not found at {self.config_path}")
            self.sources = []
            self.fallback_config = {'enabled': False}

        except Exception as e:
            logger.error(f"Failed to load authoritative sources: {e}")
            self.sources = []
            self.fallback_config = {'enabled': False}

    def find_source(self, claim_text: str) -> Optional[Dict[str, Any]]:
        """
        Find authoritative source for a claim

        Args:
            claim_text: The claim text to match

        Returns:
            Source dict with 'name', 'url', 'query_prompt' or None if no match
        """
        claim_lower = claim_text.lower()

        # Try to match against each source
        for source in self.sources:
            keywords = source.get('keywords', [])

            # Check if all keywords appear in the claim
            # (Could be enhanced to require only subset of keywords)
            if any(keyword.lower() in claim_lower for keyword in keywords):
                logger.info(f"Matched claim to source: {source.get('name')}")
                return {
                    'name': source.get('name'),
                    'url': source.get('url'),
                    'query_prompt': source.get('query_prompt')
                }

        logger.info("No authoritative source match found for claim")
        return None

    def get_fallback_config(self) -> Dict[str, Any]:
        """
        Get fallback configuration

        Returns:
            Fallback config dict
        """
        return self.fallback_config


def match_claim_to_source(claim_text: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to match claim to authoritative source

    Args:
        claim_text: The claim text

    Returns:
        Source dict or None
    """
    matcher = AuthoritativeSourceMatcher()
    return matcher.find_source(claim_text)
