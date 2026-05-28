"""Shared JSON parser for Claude responses across the context subsystem."""

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
