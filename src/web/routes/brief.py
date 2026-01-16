"""
Brief routes - generate and view daily briefings
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, url_for

bp = Blueprint("brief", __name__)
logger = logging.getLogger(__name__)


@bp.route("/")
def index():
    """Brief generation page"""
    # Get recent briefs
    recent_briefs = _get_recent_briefs()
    return render_template("brief.html", recent_briefs=recent_briefs)


@bp.route("/generate", methods=["POST"])
def generate():
    """Generate a new brief (AJAX endpoint)"""
    try:
        # Run brief generation asynchronously
        result = asyncio.run(_generate_brief())

        # Build view URL for the generated report
        html_path = result.get("html_path", "")
        view_url = ""
        if html_path:
            filename = Path(html_path).name
            view_url = url_for("brief.view", filename=filename)

        return jsonify(
            {
                "success": True,
                "message": "Brief generated successfully",
                "brief": result.get("brief", {}),
                "html_path": view_url,
                "json_path": result.get("json_path", ""),
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": str(e),
            }
        ), 500


@bp.route("/view/<path:filename>")
def view(filename):
    """View a specific brief report"""
    from ...config.settings import settings

    filepath = settings.briefings_dir / filename
    if not filepath.exists():
        return f"Report not found: {filename}", 404

    # Read and return HTML content
    return filepath.read_text()


async def _generate_brief(hours: int = 24) -> dict:
    """Generate a daily brief using the same pipeline as CLI"""
    from ...newsletter.newsletter_system import NewsletterSystem
    from ...pipeline.orchestrator import run_pipeline

    # Step 1: Run the full pipeline (fetch, deduplicate, filter, synthesize)
    # This matches the CLI behavior
    pipeline_result = await run_pipeline(
        prioritize_hours=hours,
        topic_filters=None,
        verify_trust=True,
    )

    # Step 2: Generate report from synthesis
    newsletter = NewsletterSystem()

    # Extract synthesis_id from pipeline to prevent duplicate synthesis generation
    synthesis_id = pipeline_result.get("stages", {}).get("synthesis", {}).get("synthesis_id")

    # Generate report
    result = await newsletter.generate_report(
        hours=hours,
        send_email=False,
        topic_filters=None,
        synthesis_id=synthesis_id,
        save_local=True,
    )

    # Save JSON report (matches CLI behavior)
    content_data = {
        "start_date": result.get("start_date"),
        "end_date": result.get("end_date"),
        "duration_hours": result.get("duration_hours"),
        "report_type": result.get("report_type"),
        "articles_analyzed": result.get("articles_analyzed"),
        "executive_summary": result.get("executive_summary", ""),
        "synthesis_data": result.get("synthesis_data", {}),
    }
    json_path = newsletter.save_json_report(content_data)

    # Extract brief content for display
    synthesis = result.get("synthesis_data", {})
    brief_content = {
        "bottom_line": "",
        "key_findings": [],
        "local_relevance": "",
    }

    # Handle bottom_line which may be a dict or string
    bottom_line = synthesis.get("bottom_line", "")
    if isinstance(bottom_line, dict):
        brief_content["bottom_line"] = bottom_line.get("summary", "")
    else:
        brief_content["bottom_line"] = str(bottom_line)

    # Extract key findings
    key_findings = synthesis.get("key_findings", [])
    if isinstance(key_findings, list):
        for finding in key_findings:
            if isinstance(finding, dict):
                brief_content["key_findings"].append(finding.get("finding", str(finding)))
            else:
                brief_content["key_findings"].append(str(finding))

    # Extract local relevance
    local = synthesis.get("local_relevance", "")
    if isinstance(local, dict):
        brief_content["local_relevance"] = local.get("summary", "")
    else:
        brief_content["local_relevance"] = str(local)

    # Also use executive_summary as fallback for bottom_line
    if not brief_content["bottom_line"]:
        brief_content["bottom_line"] = result.get("executive_summary", "")

    # Extract trust verification status
    trust_verification = result.get("trust_verification", {})

    return {
        "html_path": str(result.get("local_path", "")),
        "json_path": str(json_path) if json_path else "",
        "brief": brief_content,
        "trust_verified": trust_verification.get("passed", True),
        "articles_analyzed": result.get("articles_analyzed", 0),
    }


def _get_recent_briefs() -> list[dict]:
    """Get list of recent brief reports"""
    from ...config.settings import settings

    briefs = []
    briefings_dir = settings.briefings_dir

    if not briefings_dir.exists():
        return briefs

    html_files = sorted(briefings_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)

    for f in html_files[:10]:
        briefs.append(
            {
                "title": f.stem.replace("_", " ").replace("-", " ").title(),
                "filename": f.name,
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "url": url_for("brief.view", filename=f.name),
            }
        )

    return briefs
