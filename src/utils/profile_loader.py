"""
User Profile Loader for InsightWeaver

Loads and manages user context profiles for personalized narrative synthesis.
Implements fail-fast approach - requires actual user_profile.json to exist.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime


class ProfileValidationError(Exception):
    """Raised when user profile is missing required fields"""
    pass


class UserProfile:
    """Manages user context profile for personalized intelligence synthesis"""

    # Required top-level sections
    REQUIRED_SECTIONS = {
        'geographic_context',
        'professional_context',
        'civic_interests',
        'personal_priorities',
        'content_preferences'
    }

    # Required fields within each section
    REQUIRED_FIELDS = {
        'geographic_context': {'primary_location'},
        'professional_context': {'professional_domains'},
        'content_preferences': {'excluded_topics'}
    }

    def __init__(self, profile_path: Optional[str] = None):
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
        self._profile_data: Optional[Dict] = None

    def _validate_profile(self, profile_data: Dict) -> None:
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

    def load_profile(self) -> Dict:
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

        with open(self.profile_path, 'r', encoding='utf-8') as f:
            self._profile_data = json.load(f)

        # Validate profile structure
        self._validate_profile(self._profile_data)

        return self._profile_data

    @property
    def profile(self) -> Dict:
        """Get cached profile data, load if not already loaded"""
        if self._profile_data is None:
            self.load_profile()
        return self._profile_data

    def get_geographic_context(self) -> Dict:
        """Extract geographic context from profile"""
        return self.profile.get('geographic_context', {})

    def get_professional_context(self) -> Dict:
        """Extract professional context from profile"""
        return self.profile.get('professional_context', {})

    def get_civic_interests(self) -> Dict:
        """Extract civic interests from profile"""
        return self.profile.get('civic_interests', {})

    def get_personal_priorities(self) -> Dict:
        """Extract personal priorities from profile"""
        return self.profile.get('personal_priorities', {})

    def get_content_preferences(self) -> Dict:
        """Extract content preferences from profile"""
        return self.profile.get('content_preferences', {})

    def get_excluded_topics(self) -> List[str]:
        """Get list of topics to exclude from analysis"""
        return self.get_content_preferences().get('excluded_topics', [])

    def get_professional_domains(self) -> List[str]:
        """Get list of professional domains for relevance scoring"""
        return self.get_professional_context().get('professional_domains', [])

    def get_primary_location(self) -> Dict:
        """Get primary location (city, state, region)"""
        return self.get_geographic_context().get('primary_location', {})

    def get_complexity_level(self) -> str:
        """Get preferred content complexity level"""
        return self.get_content_preferences().get('complexity_level', 'balanced')

    def format_for_agent_context(self) -> str:
        """
        Format profile as contextual string for agent system prompts

        Returns:
            Formatted string suitable for inclusion in agent prompts
        """
        profile = self.profile

        # Extract key context elements
        location = self.get_primary_location()
        location_str = f"{location.get('city', '')}, {location.get('state', '')}"

        prof_context = self.get_professional_context()
        role = prof_context.get('job_role', '')
        industry = prof_context.get('industry', '')
        domains = ', '.join(self.get_professional_domains())

        civic = self.get_civic_interests()
        engagement = civic.get('political_engagement_level', 'moderate')
        policy_areas = ', '.join(civic.get('policy_areas', [])[:3])

        priorities = self.get_personal_priorities()
        priority_topics = ', '.join(priorities.get('priority_topics', [])[:5])

        excluded = ', '.join(self.get_excluded_topics())

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
        role = self.get_professional_context().get('job_role', 'Unknown')
        return f"<UserProfile: {role} in {location.get('city', 'Unknown')}>"


# Singleton instance for easy access throughout the application
_global_profile: Optional[UserProfile] = None


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