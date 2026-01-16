"""
Settings routes - view user profile and configuration
"""

import json
import os
from pathlib import Path

from flask import Blueprint, render_template

bp = Blueprint("settings", __name__)


@bp.route("/")
def index():
    """Settings overview page"""
    profile = _get_profile()
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY", ""))

    return render_template(
        "settings.html",
        profile=profile,
        has_api_key=has_api_key,
    )


def _get_profile() -> dict:
    """Load user profile"""
    profile_path = Path("config/user_profile.json")

    if not profile_path.exists():
        return {
            "geographic_context": {"primary_location": "Not configured"},
            "professional_context": {
                "industry": "Not configured",
                "job_role": "Not configured",
                "professional_domains": [],
            },
        }

    with open(profile_path) as f:
        return json.load(f)
