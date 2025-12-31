"""
Trust Layer Module
Provides trust verification for AI responses

Stage 2A: Core infrastructure
Stage 2B: Fact verification
Stage 2C: Bias analysis
Stage 2D: Intimacy detection
"""
from .trust_pipeline import TrustPipeline
from .trust_report import TrustReportFormatter
from .fact_verifier import FactVerifier, Claim, FactVerification
from .bias_analyzer import (
    BiasAnalyzer,
    BiasAnalysis,
    FramingIssue,
    Assumption,
    Omission,
    LoadedTerm
)
from .intimacy_detector import (
    IntimacyDetector,
    IntimacyAnalysis,
    IntimacyIssue
)
from .moderate_formatter import (
    format_moderate_trust_summary,
    format_compact_trust_summary,
    calculate_actionability,
    select_top_bias_issues
)

__all__ = [
    'TrustPipeline',
    'TrustReportFormatter',
    'FactVerifier',
    'Claim',
    'FactVerification',
    'BiasAnalyzer',
    'BiasAnalysis',
    'FramingIssue',
    'Assumption',
    'Omission',
    'LoadedTerm',
    'IntimacyDetector',
    'IntimacyAnalysis',
    'IntimacyIssue',
    'format_moderate_trust_summary',
    'format_compact_trust_summary',
    'calculate_actionability',
    'select_top_bias_issues'
]
