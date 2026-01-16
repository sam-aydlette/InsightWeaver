"""
Setup wizard routes - first-time configuration
"""

import contextlib
import json
import os
import stat
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

bp = Blueprint("setup", __name__)

# US States for location dropdown
US_STATES = [
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
    ("DC", "Washington DC"),
]

# Industry options
INDUSTRIES = [
    "Technology / Software",
    "Government / Public Sector",
    "Finance / Banking",
    "Healthcare / Medical",
    "Education",
    "Legal",
    "Consulting",
    "Manufacturing",
    "Retail / E-commerce",
    "Media / Entertainment",
    "Non-profit",
    "Other",
]

# Topic interest options
TOPIC_INTERESTS = [
    ("cybersecurity", "Cybersecurity"),
    ("ai_ml", "AI / Machine Learning"),
    ("local_politics", "Local Politics & Government"),
    ("economics", "Economics & Finance"),
    ("technology", "Technology & Innovation"),
    ("environment", "Environment & Climate"),
    ("healthcare", "Healthcare Policy"),
    ("education", "Education"),
    ("international", "International Affairs"),
]


def _has_api_key() -> bool:
    """Check if API key already exists in environment or .env file"""
    # Check environment variable
    if os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-"):
        return True

    # Check .env file
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("ANTHROPIC_API_KEY=sk-ant-"):
                    return True
    return False


def _get_existing_profile() -> dict | None:
    """Load existing user profile if it exists"""
    profile_path = Path("config/user_profile.json")
    if not profile_path.exists():
        return None

    try:
        with open(profile_path) as f:
            return json.load(f)
    except Exception:
        return None


@bp.route("/")
def welcome():
    """Welcome page - start of setup wizard"""
    # If everything is already configured, go straight to dashboard
    if _has_api_key() and _get_existing_profile():
        flash("Setup already complete. Redirecting to dashboard.", "info")
        return redirect(url_for("dashboard.index"))

    return render_template("setup/welcome.html")


@bp.route("/api-key", methods=["GET", "POST"])
def api_key():
    """API key configuration step"""
    # Skip if API key already exists
    if _has_api_key():
        session["setup_api_key_saved"] = True
        return redirect(url_for("setup.location"))

    if request.method == "POST":
        key = request.form.get("api_key", "").strip()

        if not key:
            flash("Please enter your Anthropic API key", "error")
            return render_template("setup/api_key.html")

        if not key.startswith("sk-ant-"):
            flash("API key should start with 'sk-ant-'. Please check your key.", "error")
            return render_template("setup/api_key.html")

        # Save API key directly to file (don't store in session for security)
        _save_api_key(key)

        # Mark that API key step is complete (without storing the key itself)
        session["setup_api_key_saved"] = True
        return redirect(url_for("setup.location"))

    return render_template("setup/api_key.html")


@bp.route("/location", methods=["GET", "POST"])
def location():
    """Location configuration step"""
    # Skip if profile already exists
    existing = _get_existing_profile()
    if existing:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()

        if not city or not state:
            flash("Please enter your city and state", "error")
            return render_template("setup/location.html", states=US_STATES)

        session["setup_city"] = city
        session["setup_state"] = state
        return redirect(url_for("setup.profession"))

    return render_template("setup/location.html", states=US_STATES)


@bp.route("/profession", methods=["GET", "POST"])
def profession():
    """Professional context configuration step"""
    # Skip if profile already exists
    existing = _get_existing_profile()
    if existing:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        industry = request.form.get("industry", "").strip()
        role = request.form.get("role", "").strip()

        if not industry:
            flash("Please select your industry", "error")
            return render_template("setup/profession.html", industries=INDUSTRIES)

        session["setup_industry"] = industry
        session["setup_role"] = role or "Professional"
        return redirect(url_for("setup.interests"))

    return render_template("setup/profession.html", industries=INDUSTRIES)


@bp.route("/interests", methods=["GET", "POST"])
def interests():
    """Topic interests configuration step"""
    # Skip if profile already exists
    existing = _get_existing_profile()
    if existing:
        return redirect(url_for("dashboard.index"))

    # Convert topic tuples to list of display names
    interest_names = [name for _, name in TOPIC_INTERESTS]

    if request.method == "POST":
        selected = request.form.getlist("interests")

        if not selected:
            flash("Please select at least one topic of interest", "error")
            return render_template("setup/interests.html", interests=interest_names)

        session["setup_interests"] = selected
        return redirect(url_for("setup.complete"))

    return render_template("setup/interests.html", interests=interest_names)


@bp.route("/complete", methods=["GET", "POST"])
def complete():
    """Final step - save configuration and finish"""
    # Skip if profile already exists
    existing = _get_existing_profile()
    if existing:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        try:
            # Save user profile (API key already saved in api_key step)
            _save_user_profile(
                city=session.get("setup_city", ""),
                state=session.get("setup_state", ""),
                industry=session.get("setup_industry", ""),
                role=session.get("setup_role", ""),
                interests=session.get("setup_interests", []),
            )

            # Initialize database
            _initialize_database()

            # Clear setup session data
            for key in list(session.keys()):
                if key.startswith("setup_"):
                    session.pop(key)

            flash("Setup complete! Welcome to InsightWeaver.", "success")
            return redirect(url_for("dashboard.index"))

        except Exception as e:
            flash(f"Error during setup: {str(e)}", "error")
            profile = {
                "city": session.get("setup_city", "Not set"),
                "state": session.get("setup_state", "Not set"),
                "industry": session.get("setup_industry", "Not set"),
                "role": session.get("setup_role", ""),
                "interests": session.get("setup_interests", []),
            }
            return render_template("setup/complete.html", profile=profile)

    # Show summary of what will be configured
    profile = {
        "city": session.get("setup_city", "Not set"),
        "state": session.get("setup_state", "Not set"),
        "industry": session.get("setup_industry", "Not set"),
        "role": session.get("setup_role", ""),
        "interests": session.get("setup_interests", []),
    }
    return render_template("setup/complete.html", profile=profile)


def _save_api_key(api_key: str):
    """
    Save API key directly to .env file with restrictive permissions.
    This is called immediately when the user submits the API key,
    avoiding storage in session/cookies.
    """
    env_path = Path(".env")
    env_content = []

    # Read existing .env if it exists
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                # Skip existing API key line
                if not line.strip().startswith("ANTHROPIC_API_KEY="):
                    env_content.append(line.rstrip())

    # Add API key
    env_content.append(f"ANTHROPIC_API_KEY={api_key}")

    # Write to file
    with open(env_path, "w") as f:
        f.write("\n".join(env_content) + "\n")

    # Set restrictive file permissions (owner read/write only)
    # This prevents other users on the system from reading the key
    # Windows may not support chmod, but file is still created
    with contextlib.suppress(OSError):
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600

    # Set in environment for immediate use
    os.environ["ANTHROPIC_API_KEY"] = api_key


def _save_user_profile(city: str, state: str, industry: str, role: str, interests: list):
    """Generate and save user profile JSON"""
    # Map state code to full name
    state_name = dict(US_STATES).get(state, state)

    professional_domains = _map_interests_to_domains(interests)

    profile = {
        "geographic_context": {
            "primary_location": f"{city}, {state_name}",
            "state": state_name,
            "areas_of_interest": [f"{city} metro area", state_name],
        },
        "professional_context": {
            "industry": industry,
            "job_role": role,
            "domains_of_expertise": [],
            "professional_domains": professional_domains,  # Required by profile loader
        },
        "civic_interests": {
            "policy_areas": [],
            "community_focus": ["local government", "schools"],
        },
        "personal_priorities": {
            "life_stage": "working professional",
            "active_decisions": [],
        },
        "content_preferences": {
            "excluded_topics": [],
            "source_preferences": {},
        },
        "feed_preferences": {
            "geographic_interests": [state.lower()],
            "professional_domains": professional_domains,  # Also here for feed matching
        },
    }

    # Ensure config directories exist
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)

    # Save profile to project config directory
    profile_path = config_dir / "user_profile.json"
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    # Also save to user home directory for CLI detection
    home_config_dir = Path.home() / ".insightweaver"
    home_config_dir.mkdir(exist_ok=True)
    home_profile_path = home_config_dir / "user_profile.json"
    with open(home_profile_path, "w") as f:
        json.dump(profile, f, indent=2)


def _map_interests_to_domains(interests: list) -> list:
    """Map interest selections to feed domain names"""
    mapping = {
        "cybersecurity": "cybersecurity",
        "ai_ml": "technology",
        "local_politics": "politics",
        "economics": "economics",
        "technology": "technology",
        "environment": "environment",
        "healthcare": "healthcare",
        "education": "education",
        "international": "international",
    }
    return [mapping.get(i, i) for i in interests]


def _initialize_database():
    """Initialize database tables"""
    from ...database.connection import create_tables

    create_tables()
