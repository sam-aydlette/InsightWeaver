"""
Collectors-specific test fixtures
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_api_response():
    """Sample API response data"""
    return {
        "items": [
            {
                "id": "item-1",
                "title": "Test Item 1",
                "description": "Description of item 1",
                "date": "2024-01-15T12:00:00Z",
            },
            {
                "id": "item-2",
                "title": "Test Item 2",
                "description": "Description of item 2",
                "date": "2024-01-15T13:00:00Z",
            },
        ]
    }


@pytest.fixture
def sample_decision_context():
    """Sample decision context for relevance scoring"""
    return {
        "active_decisions": [
            {
                "decision_id": "decision-1",
                "title": "Job Search Decision",
                "relevant_signals": ["hiring", "jobs", "employment", "career"],
            },
            {
                "decision_id": "decision-2",
                "title": "Housing Decision",
                "relevant_signals": ["housing", "rent", "mortgage", "real estate"],
            },
        ]
    }


@pytest.fixture
def mock_api_data_source():
    """Mock APIDataSource database object"""
    source = MagicMock()
    source.id = 1
    source.name = "Test API Source"
    source.source_type = "events"
    source.endpoint_url = "https://api.example.com/events"
    source.api_key_required = False
    source.is_active = True
    source.last_fetched = None
    source.error_count = 0
    source.last_error = None
    return source


@pytest.fixture
def mock_api_data_point():
    """Mock APIDataPoint database object"""
    point = MagicMock()
    point.id = 1
    point.source_id = 1
    point.data_type = "event"
    point.external_id = "event-123"
    point.title = "Test Event"
    point.description = "Event description"
    point.data_payload = {"key": "value"}
    point.event_date = datetime(2024, 1, 20, 10, 0, 0)
    point.published_date = datetime(2024, 1, 15, 12, 0, 0)
    point.expires_date = None
    point.relevance_score = 0.8
    point.decision_ids = ["decision-1"]
    point.created_at = datetime(2024, 1, 15, 12, 0, 0)
    return point


@pytest.fixture
def sample_parsed_item():
    """Sample parsed item from a collector"""
    return {
        "data_type": "event",
        "external_id": "event-123",
        "title": "Community Meeting",
        "description": "Monthly community meeting about local issues",
        "data_payload": {
            "location": "City Hall",
            "organizer": "City Council",
        },
        "event_date": datetime(2024, 1, 20, 18, 0, 0),
        "published_date": datetime(2024, 1, 15, 10, 0, 0),
    }


@pytest.fixture
def sample_job_item():
    """Sample parsed job posting item"""
    return {
        "data_type": "job_posting",
        "external_id": "job-456",
        "title": "Software Engineer",
        "description": "Hiring software engineer for our team",
        "data_payload": {
            "company": "Tech Corp",
            "salary_range": "$100k-$150k",
            "location": "Remote",
        },
        "published_date": datetime(2024, 1, 14, 9, 0, 0),
    }


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for collectors"""
    client = MagicMock()
    client.get.return_value.json.return_value = {"data": []}
    client.get.return_value.status_code = 200
    client.close = MagicMock()
    return client
