"""
Minimal Claude API Client
Simple wrapper focused on context-driven analysis
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from anthropic import Anthropic, AsyncAnthropic
from ..config.settings import settings
from .examples import get_few_shot_examples, format_examples_for_prompt

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Minimal Claude API client for context-driven analysis"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude client

        Args:
            api_key: Anthropic API key (defaults to settings.anthropic_api_key)
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = AsyncAnthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"  # Latest Sonnet model
        self.max_tokens = 4096

    async def analyze(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Send analysis request to Claude

        Args:
            system_prompt: System context and instructions
            user_message: User query/request
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Claude's response text
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": user_message
                }]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def analyze_with_context(
        self,
        context: Dict[str, Any],
        task: str,
        temperature: float = 1.0
    ) -> str:
        """
        Analyze using curated context

        Args:
            context: Curated context dictionary from ContextCurator
            task: Task description/question
            temperature: Sampling temperature

        Returns:
            Claude's response text
        """
        system_prompt = self._build_system_prompt(context)
        return await self.analyze(system_prompt, task, temperature)

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """
        Build system prompt from curated context with few-shot examples

        Args:
            context: Curated context dictionary

        Returns:
            Formatted system prompt
        """
        parts = []

        # Add user profile context
        if "user_profile" in context:
            profile = context["user_profile"]
            parts.append(f"## User Context")
            parts.append(f"Location: {profile.get('location', 'Unknown')}")
            parts.append(f"Professional Domains: {', '.join(profile.get('professional_domains', []))}")
            parts.append(f"Civic Interests: {', '.join(profile.get('civic_interests', []))}")
            parts.append("")

        # Add few-shot examples (for synthesis tasks)
        if "instructions" in context and "Perspective:" in context["instructions"]:
            parts.append(format_examples_for_prompt(get_few_shot_examples()))

        # Add recent articles context
        if "articles" in context:
            parts.append(f"## Recent Articles ({len(context['articles'])} total)")
            for i, article in enumerate(context["articles"][:20], 1):  # Limit to top 20
                parts.append(f"\n### Article {i}")
                parts.append(f"**Title:** {article.get('title', 'Untitled')}")
                parts.append(f"**Source:** {article.get('source', 'Unknown')}")
                if article.get('published_date'):
                    parts.append(f"**Date:** {article['published_date']}")
                if article.get('content'):
                    parts.append(f"**Content:** {article['content'][:500]}...")
                if article.get('entities'):
                    parts.append(f"**Entities:** {', '.join(article['entities'][:10])}")
            parts.append("")

        # Add memory/historical context
        if "memory" in context:
            parts.append("## Historical Context")
            parts.append(context["memory"])
            parts.append("")

        # Add instructions
        if "instructions" in context:
            parts.append("## Instructions")
            parts.append(context["instructions"])
            parts.append("")

        return "\n".join(parts)
