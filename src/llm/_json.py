"""Shared JSON parser for Claude responses.

Moved here from ``src/context/`` with :mod:`src.llm.claude_client` by backlog
task 012. Every caller it had was a briefing-era adjudicator and all of them
were deleted; it stays because a fenced-JSON reply is a property of the API,
not of the product that was reading it, and Tier 2 will parse the same shape.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_claude_json(response: str, label: str = "response") -> dict[str, Any]:
    """Parse a Claude JSON response, stripping any markdown code fences.

    Returns ``{}`` on parse failure and logs a warning identifying the caller
    via ``label``.
    """
    text = response.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse {label}: {e}")
        return {}
