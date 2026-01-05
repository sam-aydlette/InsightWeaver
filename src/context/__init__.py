"""
Context Engineering Module
Curates optimal token context for Claude API calls
"""

from .claude_client import ClaudeClient
from .curator import ContextCurator
from .examples import get_few_shot_examples
from .module_loader import ContextModule, ContextModuleLoader
from .perspectives import Perspective, get_perspective, list_perspectives
from .synthesizer import NarrativeSynthesizer

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
