"""
Authoritative Source Matcher
Matches claims to authoritative web sources for temporal verification
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class AuthoritativeSourceMatcher:
    """
    Matches factual claims to authoritative sources for verification
    Uses Claude for intelligent source selection
    """

    def __init__(self, config_path: str | Path | None = None, claude_client: Any = None):
        """
        Initialize source matcher

        Args:
            config_path: Path to authoritative_sources.yaml (defaults to same directory)
            claude_client: Optional ClaudeClient instance for intelligent matching
        """
        if config_path is None:
            config_path = Path(__file__).parent / "authoritative_sources.yaml"
        elif isinstance(config_path, str):
            config_path = Path(config_path)

        self.config_path: Path = config_path
        self.sources: list[dict[str, Any]] = []
        self.fallback_config: dict[str, Any] = {}
        self.claude_client = claude_client
        self._load_sources()

    def _load_sources(self):
        """Load authoritative sources from YAML config"""
        try:
            with open(self.config_path) as f:
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

    async def find_source(self, claim_text: str) -> dict[str, Any] | None:
        """
        Find authoritative source for a claim using intelligent Claude-based matching

        Uses Claude to analyze the claim and select the most appropriate authoritative
        source from the available options. Much more robust than keyword matching.

        Args:
            claim_text: The claim text to match

        Returns:
            Source dict with 'name', 'url', 'query_prompt' or None if no match
        """
        if not self.claude_client:
            logger.warning("No Claude client available, cannot intelligently match sources")
            return None

        if not self.sources:
            logger.warning("No sources loaded")
            return None

        # Format sources for Claude
        sources_list = []
        for i, source in enumerate(self.sources):
            sources_list.append({
                "id": i,
                "name": source.get('name'),
                "description": f"Keywords: {', '.join(source.get('keywords', []))}"
            })

        sources_json = json.dumps(sources_list, indent=2)

        # Ask Claude to select the best source
        matching_prompt = f"""You are analyzing a factual claim to determine which authoritative source would be best for verifying it.

CLAIM TO VERIFY:
"{claim_text}"

AVAILABLE AUTHORITATIVE SOURCES:
{sources_json}

TASK:
Analyze the claim and select the MOST APPROPRIATE authoritative source from the list above.
Consider:
- Geographic specificity (e.g., "Prime Minister of India" needs India source, not UK)
- Topic relevance (e.g., economic data needs economic source, not political)
- Organizational specificity (e.g., "CEO of Apple" needs Apple source, not Microsoft)

Respond with JSON:
{{
    "best_match_id": <number or null>,
    "confidence": <0.0-1.0>,
    "reasoning": "Brief explanation of why this source is appropriate or why no match"
}}

If no source is appropriate, set best_match_id to null."""

        try:
            result = await self.claude_client.analyze(
                system_prompt="You are a source matching specialist. Select the most appropriate authoritative source for fact verification.",
                user_message=matching_prompt,
                temperature=0.0
            )

            # Parse JSON response
            result_clean = result.strip()
            if result_clean.startswith("```json"):
                result_clean = result_clean[7:]
            elif result_clean.startswith("```"):
                result_clean = result_clean[3:]
            if result_clean.endswith("```"):
                result_clean = result_clean[:-3]
            result_clean = result_clean.strip()

            match_data = json.loads(result_clean)
            best_match_id = match_data.get("best_match_id")

            if best_match_id is not None and 0 <= best_match_id < len(self.sources):
                source = self.sources[best_match_id]
                logger.info(f"Claude matched claim to source: {source.get('name')} (confidence: {match_data.get('confidence')}, reasoning: {match_data.get('reasoning')})")

                # Check if this source requires dynamic URL construction
                if source.get('requires_country_extraction') and source.get('url_template'):
                    final_url = await self._construct_dynamic_url(claim_text, source)
                    if not final_url:
                        logger.error("Failed to construct dynamic URL for source")
                        return None
                else:
                    final_url = source.get('url')

                return {
                    'name': source.get('name'),
                    'url': final_url,
                    'query_prompt': source.get('query_prompt')
                }
            else:
                logger.info(f"Claude found no appropriate source: {match_data.get('reasoning')}")
                return None

        except Exception as e:
            logger.error(f"Source matching via Claude failed: {e}")
            return None

    async def _construct_dynamic_url(self, claim_text: str, source: dict[str, Any]) -> str | None:
        """
        Construct dynamic URL by extracting country name from claim

        Args:
            claim_text: The claim text containing a country reference
            source: Source dict with url_template

        Returns:
            Constructed URL or None if extraction fails
        """
        if not self.claude_client:
            logger.error("No Claude client for country extraction")
            return None

        url_template = source.get('url_template')
        if not url_template:
            return None

        # Ask Claude to extract the country name
        extraction_prompt = f"""Extract the country name from this claim.

CLAIM: "{claim_text}"

Respond with JSON:
{{
    "country": "The country name in standard English",
    "slug_hyphen": "URL slug with hyphens (lowercase, e.g., 'united-states', 'south-korea')",
    "slug_underscore": "URL slug with underscores (for Wikipedia, e.g., 'United_States', 'South_Korea')"
}}

Examples:
- "Who is the leader of Nicaragua?" → {{"country": "Nicaragua", "slug_hyphen": "nicaragua", "slug_underscore": "Nicaragua"}}
- "Who is president of South Africa?" → {{"country": "South Africa", "slug_hyphen": "south-africa", "slug_underscore": "South_Africa"}}
- "Leader of United Kingdom?" → {{"country": "United Kingdom", "slug_hyphen": "united-kingdom", "slug_underscore": "United_Kingdom"}}"""

        try:
            result = await self.claude_client.analyze(
                system_prompt="You are a country name extraction specialist.",
                user_message=extraction_prompt,
                temperature=0.0
            )

            # Parse JSON
            result_clean = result.strip()
            if result_clean.startswith("```json"):
                result_clean = result_clean[7:]
            elif result_clean.startswith("```"):
                result_clean = result_clean[3:]
            if result_clean.endswith("```"):
                result_clean = result_clean[:-3]
            result_clean = result_clean.strip()

            data = json.loads(result_clean)

            # Determine which slug format to use based on source
            source_name = source.get('name', '')
            if 'Wikipedia' in source_name:
                country_slug = data.get('slug_underscore')
            else:
                # Use hyphenated slug for all other sources (CIA, BBC, Reuters, etc.)
                country_slug = data.get('slug_hyphen')

            if not country_slug:
                logger.error("No country slug extracted")
                return None

            # Construct URL from template
            final_url = url_template.replace('{country}', country_slug)
            logger.info(f"Constructed dynamic URL: {final_url} (country: {data.get('country')}, source: {source_name})")
            return final_url

        except Exception as e:
            logger.error(f"Failed to extract country and construct URL: {e}")
            return None

    def find_source_sync(self, claim_text: str) -> dict[str, Any] | None:
        """
        Synchronous wrapper for find_source (for backwards compatibility)
        Uses simple keyword matching as fallback when async not available

        Args:
            claim_text: The claim text to match

        Returns:
            Source dict with 'name', 'url', 'query_prompt' or None if no match
        """
        claim_lower = claim_text.lower()

        # Simple keyword matching fallback
        best_match = None
        best_score = 0

        for source in self.sources:
            keywords = source.get('keywords', [])
            matches = sum(1 for keyword in keywords if keyword.lower() in claim_lower)

            if matches > 0:
                score = matches
                if matches == len(keywords):
                    score += 1

                if score > best_score:
                    best_score = score
                    best_match = source

        if best_match:
            logger.info(f"Keyword-matched claim to source: {best_match.get('name')} (score: {best_score})")
            return {
                'name': best_match.get('name'),
                'url': best_match.get('url'),
                'query_prompt': best_match.get('query_prompt')
            }

        logger.info("No authoritative source match found for claim")
        return None

    def get_fallback_config(self) -> dict[str, Any]:
        """
        Get fallback configuration

        Returns:
            Fallback config dict
        """
        return self.fallback_config


async def match_claim_to_source(claim_text: str) -> dict[str, Any] | None:
    """
    Convenience function to match claim to authoritative source

    Args:
        claim_text: The claim text

    Returns:
        Source dict or None
    """
    matcher = AuthoritativeSourceMatcher()
    return await matcher.find_source(claim_text)
