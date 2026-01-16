"""
Trust routes - AI chat with trust verification
"""

import asyncio
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("trust", __name__)


@bp.route("/")
def index():
    """Trust chat interface"""
    history = _get_recent_queries()
    return render_template("trust.html", history=history)


@bp.route("/query", methods=["POST"])
def query():
    """Process a trust query (AJAX endpoint)"""
    data = request.get_json()
    query_text = data.get("query", "").strip()

    if not query_text:
        return jsonify(
            {
                "success": False,
                "error": "Please enter a question",
            }
        ), 400

    try:
        result = asyncio.run(_process_query(query_text))

        return jsonify(
            {
                "success": True,
                "response": result.get("response", ""),
                "trust_report": result.get("trust_report", {}),
                "verified": result.get("verified", False),
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": str(e),
            }
        ), 500


async def _process_query(query: str) -> dict:
    """Process a trust-verified query"""
    from ...config.settings import settings
    from ...trust.trust_pipeline import TrustPipeline
    from ...trust.trust_report import TrustReportFormatter

    pipeline = TrustPipeline()

    # Run the full trust pipeline - it handles query, response, and verification
    result = await pipeline.run_full_pipeline(
        user_query=query,
        verify_response=True,
        verify_facts=True,
        check_bias=True,
        check_intimacy=True,
        temperature=0.3,  # Low temperature for factual accuracy over engagement
    )

    # Save report to central reports directory (matches CLI behavior)
    formatter = TrustReportFormatter()
    settings.trust_reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = "".join(c if c.isalnum() else "_" for c in query[:30]).strip("_")
    report_filename = f"trust_{safe_query}_{timestamp}.txt"
    report_path = settings.trust_reports_dir / report_filename

    report_content = formatter.export_to_text(result)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    # Extract analysis results
    analysis = result.get("analysis", {})

    # Format response with trust info
    return {
        "response": result.get("response", ""),
        "trust_report": {
            "fact_check": analysis.get("fact_verification", {}),
            "bias_check": analysis.get("bias_analysis", {}),
            "tone_check": analysis.get("intimacy_analysis", {}),
            "overall_trust": analysis.get("trust_score", 0),
        },
        "verified": result.get("trust_enhanced", False),
        "report_path": str(report_path),
    }


def _get_recent_queries() -> list[dict]:
    """Get recent trust query history"""
    from ...config.settings import settings

    history = []
    trust_dir = settings.trust_reports_dir

    if not trust_dir.exists():
        return history

    # Look for both .txt and .json reports
    report_files = sorted(
        list(trust_dir.glob("*.txt")) + list(trust_dir.glob("*.json")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for f in report_files[:10]:
        # Extract query from filename (trust_{query}_{timestamp}.txt)
        name_parts = f.stem.split("_")
        if len(name_parts) >= 2:
            # Skip "trust" prefix and timestamp suffix
            query_parts = name_parts[1:-2] if len(name_parts) > 3 else name_parts[1:-1]
            query_text = " ".join(query_parts).replace("_", " ")
        else:
            query_text = f.stem

        history.append(
            {
                "query": query_text[:50] + "..." if len(query_text) > 50 else query_text,
                "date": datetime.fromtimestamp(f.stat().st_mtime),
                "filename": f.name,
            }
        )

    return history
