"""
Prompt templates for InsightWeaver synthesis pipeline.

ANALYSIS_RULES.md is loaded from disk and injected into every synthesis prompt.
Frame discovery and synthesis prompts are defined as Python constants for structured output.
"""

from pathlib import Path


def load_analysis_rules() -> str:
    """Load ANALYSIS_RULES.md from the prompts directory."""
    rules_path = Path(__file__).parent / "ANALYSIS_RULES.md"
    return rules_path.read_text()
