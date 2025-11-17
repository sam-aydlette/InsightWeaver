"""
Context Engineering Module
Curates optimal token context for Claude API calls
"""

from .curator import ContextCurator
from .claude_client import ClaudeClient
from .synthesizer import NarrativeSynthesizer
from .perspectives import get_perspective, list_perspectives, Perspective
from .examples import get_few_shot_examples
from .module_loader import ContextModuleLoader, ContextModule

__all__ = [
    'ContextCurator',
    'ClaudeClient',
    'NarrativeSynthesizer',
    'get_perspective',
    'list_perspectives',
    'Perspective',
    'get_few_shot_examples',
    'ContextModuleLoader',
    'ContextModule'
]
