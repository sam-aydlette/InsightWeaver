"""
Unit tests for UserProfile loader
"""

import unittest
import json
import tempfile
from pathlib import Path
from src.utils.profile_loader import UserProfile, ProfileValidationError


class TestUserProfile(unittest.TestCase):
    """Test UserProfile loading and validation"""

    def setUp(self):
        """Create temporary profile for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.profile_path = Path(self.temp_dir) / "test_profile.json"

        self.valid_profile = {
            "profile_metadata": {"version": "1.0"},
            "geographic_context": {
                "primary_location": {"city": "Test City", "state": "TS"}
            },
            "professional_context": {
                "professional_domains": ["testing", "software"]
            },
            "civic_interests": {
                "policy_areas": ["test policy"]
            },
            "personal_priorities": {
                "priority_topics": ["topic1"]
            },
            "content_preferences": {
                "excluded_topics": ["sports"]
            }
        }

    def test_load_valid_profile(self):
        """Test loading a valid profile"""
        with open(self.profile_path, 'w') as f:
            json.dump(self.valid_profile, f)

        profile = UserProfile(str(self.profile_path))
        loaded = profile.load_profile()

        self.assertEqual(loaded['geographic_context']['primary_location']['city'], "Test City")

    def test_missing_profile_fails(self):
        """Test that missing profile raises FileNotFoundError"""
        profile = UserProfile(str(self.profile_path))

        with self.assertRaises(FileNotFoundError):
            profile.load_profile()

    def test_missing_required_sections(self):
        """Test that missing required sections raises validation error"""
        incomplete_profile = {"geographic_context": {}}

        with open(self.profile_path, 'w') as f:
            json.dump(incomplete_profile, f)

        profile = UserProfile(str(self.profile_path))

        with self.assertRaises(ProfileValidationError):
            profile.load_profile()

    def test_missing_required_fields(self):
        """Test that missing required fields in sections raises validation error"""
        profile_data = self.valid_profile.copy()
        profile_data['geographic_context'] = {}  # Missing primary_location

        with open(self.profile_path, 'w') as f:
            json.dump(profile_data, f)

        profile = UserProfile(str(self.profile_path))

        with self.assertRaises(ProfileValidationError):
            profile.load_profile()

    def test_get_professional_domains(self):
        """Test extracting professional domains"""
        with open(self.profile_path, 'w') as f:
            json.dump(self.valid_profile, f)

        profile = UserProfile(str(self.profile_path))
        profile.load_profile()

        domains = profile.get_professional_domains()
        self.assertEqual(domains, ["testing", "software"])

    def test_get_excluded_topics(self):
        """Test extracting excluded topics"""
        with open(self.profile_path, 'w') as f:
            json.dump(self.valid_profile, f)

        profile = UserProfile(str(self.profile_path))
        profile.load_profile()

        excluded = profile.get_excluded_topics()
        self.assertEqual(excluded, ["sports"])

    def test_format_for_agent_context(self):
        """Test formatting profile for agent prompts"""
        with open(self.profile_path, 'w') as f:
            json.dump(self.valid_profile, f)

        profile = UserProfile(str(self.profile_path))
        profile.load_profile()

        context = profile.format_for_agent_context()
        self.assertIn("Test City", context)
        self.assertIn("testing", context)
        self.assertIn("USER CONTEXT PROFILE", context)


if __name__ == '__main__':
    unittest.main()