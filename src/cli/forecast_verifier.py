"""
Forecast Trust Verification Helper
Verifies AI-generated forecast outputs for trustworthiness
"""

import logging
from typing import Any

from ..trust.trust_pipeline import TrustPipeline
from ..trust.trust_report import TrustReportFormatter

logger = logging.getLogger(__name__)


async def verify_forecast_horizon(horizon_text: str, horizon_name: str) -> dict[str, Any] | None:
    """
    Verify a single forecast horizon output

    Args:
        horizon_text: The forecast text for this horizon (trend description + scenarios)
        horizon_name: Name of horizon (e.g., "6-month", "1-year")

    Returns:
        Trust analysis dictionary or None if verification skipped
    """
    # Skip verification for empty content
    if not horizon_text or horizon_text.strip() == "":
        logger.info(f"Skipping trust verification for {horizon_name}: Empty content")
        return None

    # Run trust verification
    try:
        logger.info(f"Running trust verification on {horizon_name} forecast...")
        pipeline = TrustPipeline()
        analysis = await pipeline.analyze_response(
            response=horizon_text,
            verify_facts=True,
            check_bias=True,
            check_intimacy=True,
            skip_temporal_validation=True,  # Forecast predictions are speculative, not factual claims
        )
        logger.info(f"Trust verification completed for {horizon_name}")
        return analysis
    except Exception as e:
        logger.error(f"Trust verification failed for {horizon_name}: {e}", exc_info=True)
        return {"analyzed": False, "error": True, "message": f"Verification unavailable: {str(e)}"}


async def verify_forecast_aggregate(executive_text: str) -> dict[str, Any] | None:
    """
    Verify aggregate executive forecast summary

    Args:
        executive_text: The executive summary text combining all horizons

    Returns:
        Trust analysis dictionary or None if verification skipped
    """
    # Skip verification for empty content
    if not executive_text or executive_text.strip() == "":
        logger.info("Skipping trust verification: Empty executive summary")
        return None

    # Run trust verification
    try:
        logger.info("Running trust verification on forecast executive summary...")
        pipeline = TrustPipeline()
        analysis = await pipeline.analyze_response(
            response=executive_text,
            verify_facts=True,
            check_bias=True,
            check_intimacy=True,
            skip_temporal_validation=True,  # Forecast predictions are speculative
        )
        logger.info("Trust verification completed for executive summary")
        return analysis
    except Exception as e:
        logger.error(f"Trust verification failed for executive summary: {e}", exc_info=True)
        return {"analyzed": False, "error": True, "message": f"Verification unavailable: {str(e)}"}


def format_forecast_trust_section(
    analysis: dict[str, Any] | None, horizon_name: str | None = None
) -> str:
    """
    Format trust analysis for display in forecast output

    Args:
        analysis: Trust analysis dictionary or None
        horizon_name: Optional horizon name for per-horizon verification

    Returns:
        Formatted trust verification section
    """
    if analysis is None:
        return ""  # No section if verification was skipped

    lines = []
    lines.append("")
    lines.append("-" * 80)
    if horizon_name:
        lines.append(f"TRUST VERIFICATION ({horizon_name})")
    else:
        lines.append("TRUST VERIFICATION")
    lines.append("-" * 80)

    if analysis.get("error"):
        lines.append(f"\n{analysis.get('message', 'Verification unavailable')}\n")
    else:
        # Use moderate detail formatter
        formatter = TrustReportFormatter()
        moderate_summary = formatter.format_moderate_summary(analysis)
        lines.append(moderate_summary)

    return "\n".join(lines)
