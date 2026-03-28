"""
Context Engineering Module
Curates optimal token context for Claude API calls
"""

from .claude_client import ClaudeClient
from .curator import ContextCurator
from .synthesizer import NarrativeSynthesizer

__all__ = [
    "ContextCurator",
    "ClaudeClient",
    "NarrativeSynthesizer",
]
