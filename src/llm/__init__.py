"""
The Claude API boundary.

One client, one response parser. Ported out of the deleted ``src/context/``
package by backlog task 012 for Tier 2 adjudication; the synthesis product that
used to call it is gone, the call path is not.
"""

from ._json import parse_claude_json
from .claude_client import ClaudeClient

__all__ = ["ClaudeClient", "parse_claude_json"]
