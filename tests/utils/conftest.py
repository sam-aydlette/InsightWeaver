"""
Utils-specific test fixtures
"""

import json

import pytest


@pytest.fixture
def valid_user_profile():
    """Valid user profile data for testing"""
    return {
        "geographic_context": {
            "primary_location": {
                "city": "Fairfax",
                "county": "Fairfax County",
                "state": "Virginia",
                "region": "Northern Virginia",
                "country": "USA",
            },
            "secondary_locations": [],
        },
        "professional_context": {
            "professional_domains": ["cybersecurity", "software development"],
            "industry": "technology",
            "role": "engineer",
        },
        "civic_interests": {
            "policy_areas": ["education", "housing"],
            "engagement_level": "medium",
        },
        "personal_priorities": {
            "topics": ["AI", "security"],
            "time_horizon": "medium",
        },
        "content_preferences": {
            "excluded_topics": ["sports", "entertainment"],
            "preferred_sources": [],
        },
    }


@pytest.fixture
def profile_missing_section():
    """Profile missing required section"""
    return {
        "geographic_context": {
            "primary_location": {"city": "Test", "state": "VA"},
        },
        "professional_context": {
            "professional_domains": ["test"],
        },
        # Missing: civic_interests, personal_priorities, content_preferences
    }


@pytest.fixture
def profile_missing_field():
    """Profile missing required field within a section"""
    return {
        "geographic_context": {
            # Missing: primary_location
        },
        "professional_context": {
            "professional_domains": ["test"],
        },
        "civic_interests": {},
        "personal_priorities": {},
        "content_preferences": {
            "excluded_topics": [],
        },
    }


@pytest.fixture
def temp_profile_file(tmp_path, valid_user_profile):
    """Create a temporary profile file for testing"""
    profile_path = tmp_path / "user_profile.json"
    with open(profile_path, "w") as f:
        json.dump(valid_user_profile, f)
    return profile_path
