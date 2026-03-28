"""
User Profile Loader for InsightWeaver

Loads and manages user context profiles for personalized narrative synthesis.
Implements fail-fast approach - requires actual user_profile.json to exist.
"""

import json
from pathlib import Path


class ProfileValidationError(Exception):
    """Raised when user profile is missing required fields"""

    pass


class UserProfile:
    """Manages user context profile for personalized intelligence synthesis"""

    # Required top-level sections
    REQUIRED_SECTIONS = {
        "geographic_context",
        "professional_context",
        "civic_interests",
        "personal_priorities",
        "content_preferences",
    }

    # Required fields within each section
    REQUIRED_FIELDS = {
        "geographic_context": {"primary_location"},
        "professional_context": {"professional_domains"},
        "content_preferences": {"excluded_topics"},
    }

    def __init__(self, profile_path: str | None = None):
        """
        Initialize profile loader

        Args:
            profile_path: Path to user_profile.json (defaults to config/user_profile.json)
        """
        if profile_path is None:
            # Default to config/user_profile.json relative to project root
            project_root = Path(__file__).parent.parent.parent
            profile_path = project_root / "config" / "user_profile.json"

        self.profile_path = Path(profile_path)
        self._profile_data: dict | None = None

    def _validate_profile(self, profile_data: dict) -> None:
        """
        Validate that profile contains required sections and fields

        Args:
            profile_data: Loaded profile dictionary

        Raises:
            ProfileValidationError: If required sections or fields are missing
        """
        missing_sections = self.REQUIRED_SECTIONS - set(profile_data.keys())
        if missing_sections:
            raise ProfileValidationError(
                f"User profile missing required sections: {', '.join(missing_sections)}"
            )

        # Validate required fields within each section
        for section, required_fields in self.REQUIRED_FIELDS.items():
            if section in profile_data:
                section_data = profile_data[section]
                missing_fields = required_fields - set(section_data.keys())
                if missing_fields:
                    raise ProfileValidationError(
                        f"Section '{section}' missing required fields: {', '.join(missing_fields)}"
                    )

    def load_profile(self) -> dict:
        """
        Load user profile from JSON file

        Returns:
            Dict containing full profile data

        Raises:
            FileNotFoundError: If user_profile.json does not exist (fail-fast)
            json.JSONDecodeError: If profile JSON is malformed
            ProfileValidationError: If required sections or fields are missing
        """
        if not self.profile_path.exists():
            raise FileNotFoundError(
                f"User profile not found at {self.profile_path}. "
                f"Please create config/user_profile.json from the example template. "
                f"See config/user_profile.example.json"
            )

        with open(self.profile_path, encoding="utf-8") as f:
            self._profile_data = json.load(f)

        # Validate profile structure
        self._validate_profile(self._profile_data)

        return self._profile_data

    @property
    def profile(self) -> dict:
        """Get cached profile data, load if not already loaded"""
        if self._profile_data is None:
            self.load_profile()
        return self._profile_data

    def get_geographic_context(self) -> dict:
        """Extract geographic context from profile"""
        return self.profile.get("geographic_context", {})

    def get_professional_context(self) -> dict:
        """Extract professional context from profile"""
        return self.profile.get("professional_context", {})

    def get_civic_interests(self) -> dict:
        """Extract civic interests from profile"""
        return self.profile.get("civic_interests", {})

    def get_personal_priorities(self) -> dict:
        """Extract personal priorities from profile"""
        return self.profile.get("personal_priorities", {})

    def get_content_preferences(self) -> dict:
        """Extract content preferences from profile"""
        return self.profile.get("content_preferences", {})

    def get_excluded_topics(self) -> list[str]:
        """Get list of topics to exclude from analysis"""
        return self.get_content_preferences().get("excluded_topics", [])

    def get_professional_domains(self) -> list[str]:
        """Get list of professional domains for relevance scoring"""
        return self.get_professional_context().get("professional_domains", [])

    def get_primary_location(self) -> dict:
        """Get primary location (city, state, region)"""
        return self.get_geographic_context().get("primary_location", {})

    def get_complexity_level(self) -> str:
        """Get preferred content complexity level"""
        return self.get_content_preferences().get("complexity_level", "balanced")

    def get_voting_context(self) -> dict:
        """
        Get voting context (districts, precinct, address)

        Returns dict with keys:
        - registered_state: Two-letter state code (e.g., "VA")
        - county_fips: FIPS code for county
        - congressional_district: e.g., "VA-11"
        - state_senate_district: State senate district number
        - state_house_district: State house/delegate district number
        - school_district: School district name
        - address: Dict with street, city, state, zip
        """
        return self.profile.get("voting_context", {})

    def get_civic_preferences(self) -> dict:
        """
        Get civic tracking preferences

        Returns dict with keys:
        - track_elections: bool
        - track_meetings: bool
        - track_public_comments: bool
        - track_budget_hearings: bool
        - track_zoning: bool
        - advance_notice_days: int (default 7)
        """
        return self.profile.get("civic_preferences", {})

    def get_active_decisions(self) -> list[dict]:
        """
        Get list of active decisions in structured format

        Supports both old format (list of strings) and new format (list of dicts).
        Old format is converted to new format for consistency.

        Returns list of dicts with keys:
        - name: Decision name/description
        - key_factors: List of factors to track
        - decision_type: Type (career, housing, education, financial, civic)
        - created_at: When the decision was added
        """
        priorities = self.get_personal_priorities()
        decisions = priorities.get("active_decisions", [])

        # Normalize to structured format
        normalized = []
        for decision in decisions:
            if isinstance(decision, str):
                # Old format: convert string to dict
                normalized.append(
                    {
                        "name": decision,
                        "key_factors": [],
                        "decision_type": self._infer_decision_type(decision),
                        "created_at": None,
                    }
                )
            elif isinstance(decision, dict):
                # New format: ensure all fields present
                normalized.append(
                    {
                        "name": decision.get("name", "Unknown"),
                        "key_factors": decision.get("key_factors", []),
                        "decision_type": decision.get(
                            "decision_type", self._infer_decision_type(decision.get("name", ""))
                        ),
                        "created_at": decision.get("created_at"),
                    }
                )

        return normalized

    def _infer_decision_type(self, name: str) -> str:
        """Infer decision type from name if not specified."""
        name_lower = name.lower()
        if any(kw in name_lower for kw in ["career", "job", "work", "salary", "role"]):
            return "career"
        elif any(kw in name_lower for kw in ["housing", "home", "apartment", "rent", "mortgage"]):
            return "housing"
        elif any(kw in name_lower for kw in ["school", "education", "learning", "degree"]):
            return "education"
        elif any(kw in name_lower for kw in ["money", "invest", "financial", "savings"]):
            return "financial"
        elif any(kw in name_lower for kw in ["vote", "election", "policy", "civic"]):
            return "civic"
        return "other"

    def get_source_calibration(self) -> dict:
        """
        Get source calibration settings

        Returns dict with keys:
        - trust_overrides: Dict of source_name -> override_value
        - calibration_alerts_enabled: bool
        - alert_threshold_deviation: float (how far from tracked trust to trigger alert)
        """
        return self.profile.get(
            "source_calibration",
            {
                "trust_overrides": {},
                "calibration_alerts_enabled": True,
                "alert_threshold_deviation": 0.2,
            },
        )

    def get_source_trust_override(self, source_name: str) -> float | None:
        """
        Get user's trust override for a specific source

        Args:
            source_name: Name of the source

        Returns:
            Override trust value (0.0-1.0) or None if no override set
        """
        calibration = self.get_source_calibration()
        return calibration.get("trust_overrides", {}).get(source_name)

    def get_districts(self) -> list[str]:
        """
        Get list of all electoral districts for the user

        Returns list like ["VA-11", "SD-32", "HD-36"]
        """
        voting = self.get_voting_context()
        districts = []
        if cd := voting.get("congressional_district"):
            districts.append(cd)
        if sd := voting.get("state_senate_district"):
            districts.append(f"SD-{sd}")
        if hd := voting.get("state_house_district"):
            districts.append(f"HD-{hd}")
        return districts

    def has_voting_context(self) -> bool:
        """Check if user has configured voting context"""
        voting = self.get_voting_context()
        return bool(voting.get("registered_state") or voting.get("address"))

    def format_for_agent_context(self) -> str:
        """
        Format profile as contextual string for agent system prompts

        Returns:
            Formatted string suitable for inclusion in agent prompts
        """
        # Extract key context elements
        location = self.get_primary_location()
        # Handle both string and dict formats for primary_location
        if isinstance(location, str):
            location_str = location
        elif isinstance(location, dict):
            location_str = f"{location.get('city', '')}, {location.get('state', '')}"
        else:
            location_str = "Unknown"

        prof_context = self.get_professional_context()
        role = prof_context.get("job_role", "")
        industry = prof_context.get("industry", "")
        domains = ", ".join(self.get_professional_domains())

        civic = self.get_civic_interests()
        engagement = civic.get("political_engagement_level", "moderate")
        policy_areas = ", ".join(civic.get("policy_areas", [])[:3])

        priorities = self.get_personal_priorities()
        priority_topics = ", ".join(priorities.get("priority_topics", [])[:5])

        excluded = ", ".join(self.get_excluded_topics())

        context_str = f"""USER CONTEXT PROFILE:

Location: {location_str}
Professional Role: {role} in {industry}
Professional Domains: {domains}
Civic Engagement: {engagement} - Focus on {policy_areas}
Priority Topics: {priority_topics}
Excluded Topics: {excluded}
Content Complexity: {self.get_complexity_level()}

Use this context to filter, prioritize, and frame all analysis through the user's specific circumstances and interests."""

        return context_str

    def __repr__(self) -> str:
        location = self.get_primary_location()
        role = self.get_professional_context().get("job_role", "Unknown")
        # Handle both string and dict formats for primary_location
        if isinstance(location, str):
            location_str = location
        elif isinstance(location, dict):
            location_str = location.get("city", "Unknown")
        else:
            location_str = "Unknown"
        return f"<UserProfile: {role} in {location_str}>"


# Singleton instance for easy access throughout the application
_global_profile: UserProfile | None = None


def get_user_profile() -> UserProfile:
    """
    Get global UserProfile instance (singleton pattern)

    Returns:
        UserProfile instance
    """
    global _global_profile
    if _global_profile is None:
        _global_profile = UserProfile()
    return _global_profile


def reload_profile() -> UserProfile:
    """
    Force reload of user profile (useful for testing or after profile updates)

    Returns:
        Newly loaded UserProfile instance
    """
    global _global_profile
    _global_profile = UserProfile()
    _global_profile.load_profile()
    return _global_profile
