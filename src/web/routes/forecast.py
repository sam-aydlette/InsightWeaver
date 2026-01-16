"""
Forecast routes - generate and view forecasts
"""

import asyncio
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, url_for

bp = Blueprint("forecast", __name__)


@bp.route("/")
def index():
    """Forecast generation page"""
    recent_forecasts = _get_recent_forecasts()
    return render_template("forecast.html", recent_forecasts=recent_forecasts)


@bp.route("/generate", methods=["POST"])
def generate():
    """Generate a new forecast (AJAX endpoint)"""
    try:
        result = asyncio.run(_generate_forecast())

        # Build view URL for the generated report
        html_path = result.get("html_path", "")
        view_url = ""
        if html_path:
            filename = Path(html_path).name
            view_url = url_for("forecast.view", filename=filename)

        return jsonify(
            {
                "success": True,
                "message": "Forecast generated successfully",
                "html_path": view_url,
                "json_path": result.get("json_path"),
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
    """View a specific forecast report"""
    from ...config.settings import settings

    filepath = settings.forecasts_dir / filename
    if not filepath.exists():
        return f"Report not found: {filename}", 404

    return filepath.read_text()


async def _generate_forecast() -> dict:
    """Generate a certainty-based forecast"""
    from ...forecast.formatter import ForecastFormatter
    from ...forecast.orchestrator import ForecastOrchestrator
    from ...utils.profile_loader import get_user_profile

    user_profile = get_user_profile()
    orchestrator = ForecastOrchestrator(user_profile=user_profile)

    result = await orchestrator.run_forecast()

    formatter = ForecastFormatter()
    html_path = formatter.save_html_report(result)
    json_path = formatter.save_json_report(result)

    return {
        "html_path": str(html_path),
        "json_path": str(json_path),
    }


def _get_recent_forecasts() -> list[dict]:
    """Get list of recent forecast reports"""
    from ...config.settings import settings

    forecasts = []
    forecasts_dir = settings.forecasts_dir

    if not forecasts_dir.exists():
        return forecasts

    html_files = sorted(forecasts_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)

    for f in html_files[:10]:
        forecasts.append(
            {
                "name": f.stem.replace("_", " ").replace("-", " ").title(),
                "filename": f.name,
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "url": url_for("forecast.view", filename=f.name),
            }
        )

    return forecasts
