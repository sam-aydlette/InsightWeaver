"""
Dashboard routes - main landing page after setup
"""

from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
def index():
    """Main dashboard page"""
    # Get recent reports
    recent_reports = _get_recent_reports()

    # Get user profile summary
    profile = _get_profile_summary()

    return render_template(
        "dashboard.html",
        recent_reports=recent_reports,
        profile=profile,
        now=datetime.now(),
    )


def _get_recent_reports() -> list[dict]:
    """Get list of recent reports"""
    reports = []

    # Check briefings
    briefings_dir = Path("reports/briefings")
    if briefings_dir.exists():
        html_files = sorted(
            briefings_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for f in html_files[:3]:
            reports.append(
                {
                    "type": "brief",
                    "name": f.stem,
                    "path": str(f),
                    "date": datetime.fromtimestamp(f.stat().st_mtime),
                }
            )

    # Check forecasts
    forecasts_dir = Path("reports/forecasts")
    if forecasts_dir.exists():
        html_files = sorted(
            forecasts_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for f in html_files[:3]:
            reports.append(
                {
                    "type": "forecast",
                    "name": f.stem,
                    "path": str(f),
                    "date": datetime.fromtimestamp(f.stat().st_mtime),
                }
            )

    # Sort by date
    reports.sort(key=lambda r: r["date"], reverse=True)
    return reports[:5]


def _get_profile_summary() -> dict | None:
    """Get summary of user profile for dashboard display"""
    import json

    profile_path = Path("config/user_profile.json")
    if not profile_path.exists():
        return None

    try:
        with open(profile_path) as f:
            profile = json.load(f)

        geographic = profile.get("geographic_context", {})
        professional = profile.get("professional_context", {})
        feed_prefs = profile.get("feed_preferences", {})

        # Parse city and state from primary_location ("City, State")
        primary_location = geographic.get("primary_location", "")
        if ", " in primary_location:
            city, state = primary_location.rsplit(", ", 1)
        else:
            city = primary_location
            state = geographic.get("state", "")

        return {
            "city": city or "Not set",
            "state": state or "Not set",
            "industry": professional.get("industry", "Not set"),
            "role": professional.get("job_role", ""),
            "interests": feed_prefs.get("professional_domains", []),
        }
    except Exception:
        return None
