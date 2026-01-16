"""
Tests for error handling utilities
"""


from src.utils.error_handling import (
    APIError,
    AuthenticationError,
    ClaudeAPIError,
    ConfigurationError,
    DatabaseError,
    DataError,
    InsightWeaverError,
    ParsingError,
    RateLimitError,
    ValidationError,
)


class TestInsightWeaverError:
    """Tests for base InsightWeaverError"""

    def test_create_with_message(self):
        """Should create error with message"""
        error = InsightWeaverError("Test error message")

        assert str(error) == "Test error message"
        assert error.message == "Test error message"

    def test_create_with_context(self):
        """Should create error with context"""
        context = {"key": "value", "number": 42}
        error = InsightWeaverError("Test error", context=context)

        assert error.context == context
        assert error.context["key"] == "value"

    def test_default_context_is_empty_dict(self):
        """Context should default to empty dict"""
        error = InsightWeaverError("Test error")

        assert error.context == {}
        assert isinstance(error.context, dict)


class TestAPIError:
    """Tests for APIError"""

    def test_inherits_from_base(self):
        """APIError should inherit from InsightWeaverError"""
        error = APIError("API error")

        assert isinstance(error, InsightWeaverError)
        assert isinstance(error, Exception)


class TestClaudeAPIError:
    """Tests for ClaudeAPIError"""

    def test_create_with_status_code(self):
        """Should store status code"""
        error = ClaudeAPIError("Claude error", status_code=429)

        assert error.status_code == 429
        assert error.message == "Claude error"

    def test_create_without_status_code(self):
        """Status code should be optional"""
        error = ClaudeAPIError("Claude error")

        assert error.status_code is None

    def test_inherits_from_api_error(self):
        """Should inherit from APIError"""
        error = ClaudeAPIError("Claude error")

        assert isinstance(error, APIError)
        assert isinstance(error, InsightWeaverError)


class TestRateLimitError:
    """Tests for RateLimitError"""

    def test_create_with_retry_after(self):
        """Should store retry_after value"""
        error = RateLimitError("Rate limited", retry_after=60)

        assert error.retry_after == 60

    def test_default_message(self):
        """Should have default message"""
        error = RateLimitError()

        assert "Rate limit exceeded" in error.message

    def test_inherits_from_api_error(self):
        """Should inherit from APIError"""
        error = RateLimitError()

        assert isinstance(error, APIError)


class TestAuthenticationError:
    """Tests for AuthenticationError"""

    def test_inherits_from_api_error(self):
        """Should inherit from APIError"""
        error = AuthenticationError("Auth failed")

        assert isinstance(error, APIError)


class TestDataError:
    """Tests for DataError"""

    def test_inherits_from_base(self):
        """Should inherit from InsightWeaverError"""
        error = DataError("Data error")

        assert isinstance(error, InsightWeaverError)


class TestValidationError:
    """Tests for ValidationError"""

    def test_inherits_from_data_error(self):
        """Should inherit from DataError"""
        error = ValidationError("Validation failed")

        assert isinstance(error, DataError)
        assert isinstance(error, InsightWeaverError)


class TestParsingError:
    """Tests for ParsingError"""

    def test_inherits_from_data_error(self):
        """Should inherit from DataError"""
        error = ParsingError("Parse failed")

        assert isinstance(error, DataError)


class TestDatabaseError:
    """Tests for DatabaseError"""

    def test_inherits_from_base(self):
        """Should inherit from InsightWeaverError"""
        error = DatabaseError("DB error")

        assert isinstance(error, InsightWeaverError)


class TestConfigurationError:
    """Tests for ConfigurationError"""

    def test_inherits_from_base(self):
        """Should inherit from InsightWeaverError"""
        error = ConfigurationError("Config error")

        assert isinstance(error, InsightWeaverError)


class TestExceptionHierarchy:
    """Tests for exception hierarchy relationships"""

    def test_can_catch_all_with_base(self):
        """Should be able to catch all custom exceptions with base class"""
        errors = [
            InsightWeaverError("base"),
            APIError("api"),
            ClaudeAPIError("claude"),
            RateLimitError(),
            AuthenticationError("auth"),
            DataError("data"),
            ValidationError("validation"),
            ParsingError("parsing"),
            DatabaseError("db"),
            ConfigurationError("config"),
        ]

        for error in errors:
            assert isinstance(error, InsightWeaverError)

    def test_can_catch_api_errors_together(self):
        """Should be able to catch API errors with APIError"""
        api_errors = [
            APIError("api"),
            ClaudeAPIError("claude"),
            RateLimitError(),
            AuthenticationError("auth"),
        ]

        for error in api_errors:
            assert isinstance(error, APIError)

    def test_can_catch_data_errors_together(self):
        """Should be able to catch data errors with DataError"""
        data_errors = [
            DataError("data"),
            ValidationError("validation"),
            ParsingError("parsing"),
        ]

        for error in data_errors:
            assert isinstance(error, DataError)
