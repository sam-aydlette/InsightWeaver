"""
LLM access. One client, one audited send path.

``parse_claude_json`` survives from the briefing product because a fenced-JSON
reply is a property of the API, not of the product that was reading it. Note
that it returns ``{}`` on a parse failure: that is a silent default, and Tier 2
adjudication (backlog task 016) must not use it -- a response that fails
validation is recorded as a failed adjudication, never coerced. Noted
2026-09-22 (task 026).
"""

from ._json import parse_claude_json
from .audit import record_error, record_request, record_response
from .claude_client import ClaudeClient, ModelResponse

__all__ = [
    "ClaudeClient",
    "ModelResponse",
    "parse_claude_json",
    "record_error",
    "record_request",
    "record_response",
]
