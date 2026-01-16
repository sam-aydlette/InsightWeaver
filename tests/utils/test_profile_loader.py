"""
Tests for user profile loader
"""

import json

import pytest

from src.utils.profile_loader import ProfileValidationError, UserProfile


class TestUserProfileInit:
    """Tests for UserProfile initialization"""

    def test_init_with_custom_path(self, tmp_path):
        """Should accept custom profile path"""
        custom_path = tmp_path / "custom_profile.json"
        profile = UserProfile(profile_path=str(custom_path))

        assert profile.profile_path == custom_path

    def test_init_with_default_path(self):
        """Should use default path when none provided"""
        profile = UserProfile()

        assert "user_profile.json" in str(profile.profile_path)
        assert "config" in str(profile.profile_path)


class TestLoadProfile:
    """Tests for profile loading"""

    def test_load_valid_profile(self, temp_profile_file, valid_user_profile):
        """Should load valid profile successfully"""
        profile = UserProfile(profile_path=str(temp_profile_file))
        result = profile.load_profile()

        assert result is not None
        assert "geographic_context" in result
        assert "professional_context" in result

    def test_load_nonexistent_file_raises(self, tmp_path):
        """Should raise FileNotFoundError for missing file"""
        nonexistent = tmp_path / "nonexistent.json"
        profile = UserProfile(profile_path=str(nonexistent))

        with pytest.raises(FileNotFoundError):
            profile.load_profile()

    def test_load_invalid_json_raises(self, tmp_path):
        """Should raise JSONDecodeError for invalid JSON"""
        bad_json = tmp_path / "bad.json"
        with open(bad_json, "w") as f:
            f.write("{invalid json")

        profile = UserProfile(profile_path=str(bad_json))

        with pytest.raises(json.JSONDecodeError):
            profile.load_profile()


class TestProfileValidation:
    """Tests for profile validation"""

    def test_validate_missing_section_raises(self, tmp_path, profile_missing_section):
        """Should raise ProfileValidationError for missing sections"""
        profile_path = tmp_path / "profile.json"
        with open(profile_path, "w") as f:
            json.dump(profile_missing_section, f)

        profile = UserProfile(profile_path=str(profile_path))

        with pytest.raises(ProfileValidationError) as exc_info:
            profile.load_profile()

        assert "missing required sections" in str(exc_info.value)

    def test_validate_missing_field_raises(self, tmp_path, profile_missing_field):
        """Should raise ProfileValidationError for missing fields"""
        profile_path = tmp_path / "profile.json"
        with open(profile_path, "w") as f:
            json.dump(profile_missing_field, f)

        profile = UserProfile(profile_path=str(profile_path))

        with pytest.raises(ProfileValidationError) as exc_info:
            profile.load_profile()

        assert "missing required fields" in str(exc_info.value)


class TestRequiredSections:
    """Tests for required sections constant"""

    def test_required_sections_defined(self):
        """Should have required sections defined"""
        assert hasattr(UserProfile, "REQUIRED_SECTIONS")
        assert isinstance(UserProfile.REQUIRED_SECTIONS, set)

    def test_required_sections_contents(self):
        """Should include expected sections"""
        expected = {
            "geographic_context",
            "professional_context",
            "civic_interests",
            "personal_priorities",
            "content_preferences",
        }
        assert expected == UserProfile.REQUIRED_SECTIONS


class TestRequiredFields:
    """Tests for required fields constant"""

    def test_required_fields_defined(self):
        """Should have required fields defined"""
        assert hasattr(UserProfile, "REQUIRED_FIELDS")
        assert isinstance(UserProfile.REQUIRED_FIELDS, dict)

    def test_geographic_context_required_fields(self):
        """Geographic context should require primary_location"""
        assert "geographic_context" in UserProfile.REQUIRED_FIELDS
        assert "primary_location" in UserProfile.REQUIRED_FIELDS["geographic_context"]

    def test_professional_context_required_fields(self):
        """Professional context should require professional_domains"""
        assert "professional_context" in UserProfile.REQUIRED_FIELDS
        assert "professional_domains" in UserProfile.REQUIRED_FIELDS["professional_context"]

    def test_content_preferences_required_fields(self):
        """Content preferences should require excluded_topics"""
        assert "content_preferences" in UserProfile.REQUIRED_FIELDS
        assert "excluded_topics" in UserProfile.REQUIRED_FIELDS["content_preferences"]


class TestProfileProperty:
    """Tests for profile property access"""

    def test_profile_property(self, temp_profile_file, valid_user_profile):
        """Should access profile data after loading"""
        profile = UserProfile(profile_path=str(temp_profile_file))
        profile.load_profile()

        # After loading, profile data should be accessible
        assert profile._profile_data is not None
        assert profile._profile_data["geographic_context"]["primary_location"]["city"] == "Fairfax"


class TestProfileValidationError:
    """Tests for ProfileValidationError"""

    def test_is_exception(self):
        """Should be an Exception subclass"""
        error = ProfileValidationError("Test error")

        assert isinstance(error, Exception)

    def test_message(self):
        """Should store message"""
        error = ProfileValidationError("Missing fields")

        assert str(error) == "Missing fields"
