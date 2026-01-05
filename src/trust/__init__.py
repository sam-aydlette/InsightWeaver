"""
Trust Layer Module
Provides trust verification for AI responses

Stage 2A: Core infrastructure
Stage 2B: Fact verification
Stage 2C: Bias analysis
Stage 2D: Intimacy detection
"""
from .bias_analyzer import (
    Assumption,
    BiasAnalysis,
    BiasAnalyzer,
    FramingIssue,
    LoadedTerm,
    Omission,
)
from .fact_verifier import Claim, FactVerification, FactVerifier
from .intimacy_detector import IntimacyAnalysis, IntimacyDetector, IntimacyIssue
from .moderate_formatter import (
    calculate_actionability,
    format_compact_trust_summary,
    format_moderate_trust_summary,
    select_top_bias_issues,
)
from .trust_pipeline import TrustPipeline
from .trust_report import TrustReportFormatter

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
