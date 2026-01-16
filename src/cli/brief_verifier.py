"""
Brief Trust Verification Helper
Verifies AI-generated brief outputs for trustworthiness
"""

import logging
from typing import Any

from ..trust.trust_pipeline import TrustPipeline
from ..trust.trust_report import TrustReportFormatter

logger = logging.getLogger(__name__)


async def verify_brief_output(executive_summary: str) -> dict[str, Any] | None:
    """
    Verify executive summary from brief

    Args:
        executive_summary: The AI-generated executive summary text

    Returns:
        Trust analysis dictionary or None if verification skipped
    """
    # Skip verification for empty or error content
    if not executive_summary or executive_summary.strip() == "":
        logger.info("Skipping trust verification: Empty executive summary")
        return None

    if executive_summary.startswith("No articles found") or executive_summary.startswith("Error"):
        logger.info("Skipping trust verification: Error or no-content state")
        return None

    # Run trust verification
    try:
        logger.info("Running trust verification on brief executive summary...")
        pipeline = TrustPipeline()
        analysis = await pipeline.analyze_response(executive_summary)
        logger.info("Trust verification completed successfully")
        return analysis
    except Exception as e:
        logger.error(f"Trust verification failed: {e}", exc_info=True)
        return {"analyzed": False, "error": True, "message": f"Verification unavailable: {str(e)}"}


def format_brief_trust_section(analysis: dict[str, Any] | None) -> str:
    """
    Format trust analysis for display in brief output

    Args:
        analysis: Trust analysis dictionary or None

    Returns:
        Formatted trust verification section
    """
    if analysis is None:
        return ""  # No section if verification was skipped

    lines = []
    lines.append("")
    lines.append("=" * 80)
    lines.append("TRUST VERIFICATION")
    lines.append("=" * 80)

    if analysis.get("error"):
        lines.append(f"\n{analysis.get('message', 'Verification unavailable')}\n")
    else:
        # Use moderate detail formatter
        formatter = TrustReportFormatter()
        moderate_summary = formatter.format_moderate_summary(analysis)
        lines.append(moderate_summary)

    return "\n".join(lines)
