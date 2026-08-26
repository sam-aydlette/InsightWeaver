"""
Minimal Claude API Client
Simple wrapper focused on context-driven analysis
"""

import logging
from typing import Any

from anthropic import AsyncAnthropic

from ..config.settings import settings

logger = logging.getLogger(__name__)


def _response_text(response) -> str:
    """Pull the assistant's text out of a response.

    Added 2026-08-26. ``content[0].text`` was correct when the model did not
    think: the first block was always the text. This model thinks by default,
    so ``content[0]`` is a ThinkingBlock and indexing it raises AttributeError
    -- which is what happened on the first live run after the model migration.
    The block list is heterogeneous; select by type rather than by position.

    A refusal is raised rather than returned. Returning empty string would let
    a refused analysis flow downstream as if the model had simply found
    nothing to say, which is a different and much quieter failure.
    """
    if getattr(response, "stop_reason", None) == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise RuntimeError(f"Model declined the request (category: {category})")

    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    if not parts:
        kinds = [getattr(b, "type", "?") for b in response.content]
        raise RuntimeError(f"No text block in response; got blocks: {kinds}")
    return "".join(parts)


class ClaudeClient:
    """Minimal Claude API client for context-driven analysis"""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize Claude client

        Args:
            api_key: Anthropic API key (defaults to settings.anthropic_api_key)
            model: Model id to use; defaults to Sonnet for synthesis workloads.
                Pass a Haiku id for cheap classification / matching calls.
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.client = AsyncAnthropic(api_key=self.api_key, timeout=300.0)
        # Changed 2026-08-26: claude-sonnet-4-20250514 was RETIRED on 2026-06-15 and
        # returns 404. Every synthesis run since then has failed at the API call. The
        # documented replacement for that model is claude-sonnet-5.
        self.model = model or "claude-sonnet-5"
        # Raised from 16384 the same day. max_tokens caps thinking AND response text
        # together, and this model thinks by default, so the old ceiling would truncate
        # a full-length synthesis mid-answer. Its tokenizer also produces more tokens
        # for the same text than the retired model's did.
        self.max_tokens = 32000

    async def analyze(
        self,
        system_prompt: str,
        user_message: str,
        effort: str = "high",
        max_tokens: int | None = None,
    ) -> str:
        """
        Send analysis request to Claude

        Args:
            system_prompt: System context and instructions
            user_message: User query/request
            effort: Reasoning depth -- "low" | "medium" | "high" | "xhigh" | "max"
            max_tokens: Maximum tokens in response

        Returns:
            Claude's response text
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                # Sent via extra_body: the pinned SDK predates output_config as a
                # named parameter and raises TypeError on it, but forwards extra_body
                # into the request unchanged. Added 2026-08-26 -- once the SDK pin
                # moves past that, this becomes output_config={"effort": effort}.
                extra_body={"output_config": {"effort": effort}},
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            return _response_text(response)

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def analyze_conversation(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        effort: str = "high",
        max_tokens: int | None = None,
    ) -> str:
        """
        Send conversation request to Claude with message history

        Args:
            system_prompt: System context and instructions
            messages: List of message dicts with 'role' and 'content' keys
                      Roles must alternate: user, assistant, user, assistant...
            effort: Reasoning depth -- "low" | "medium" | "high" | "xhigh" | "max"
            max_tokens: Maximum tokens in response

        Returns:
            Claude's response text
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                # Sent via extra_body: the pinned SDK predates output_config as a
                # named parameter and raises TypeError on it, but forwards extra_body
                # into the request unchanged. Added 2026-08-26 -- once the SDK pin
                # moves past that, this becomes output_config={"effort": effort}.
                extra_body={"output_config": {"effort": effort}},
                system=system_prompt,
                messages=messages,
            )

            return _response_text(response)

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def analyze_with_context(
        self, context: dict[str, Any], task: str, effort: str = "high"
    ) -> str:
        """
        Analyze using curated context

        Args:
            context: Curated context dictionary from ContextCurator
            task: Task description/question
            effort: Reasoning depth

        Returns:
            Claude's response text
        """
        system_prompt = self._build_system_prompt(context)
        return await self.analyze(system_prompt, task, effort)

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
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
            parts.append("## User Context")
            parts.append(f"Location: {profile.get('location', 'Unknown')}")
            parts.append(
                f"Professional Domains: {', '.join(profile.get('professional_domains', []))}"
            )
            parts.append(f"Civic Interests: {', '.join(profile.get('civic_interests', []))}")
            parts.append("")

        # Add recent articles context
        if "articles" in context:
            parts.append(f"## Recent Articles ({len(context['articles'])} total)")
            for i, article in enumerate(context["articles"][:20], 1):  # Limit to top 20
                parts.append(f"\n### Article {i}")
                parts.append(f"**Title:** {article.get('title', 'Untitled')}")
                parts.append(f"**Source:** {article.get('source', 'Unknown')}")
                if article.get("published_date"):
                    parts.append(f"**Date:** {article['published_date']}")
                if article.get("content"):
                    parts.append(f"**Content:** {article['content'][:500]}...")
                if article.get("entities"):
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
