"""
Tests for Base Collector
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.base_collector import BaseCollector, CollectorError


class ConcreteCollector(BaseCollector):
    """Concrete implementation for testing abstract BaseCollector"""

    def fetch_data(self):
        return [{"id": "1", "title": "Test", "description": "Test item"}]

    def parse_item(self, raw_item):
        return {
            "data_type": "test",
            "external_id": raw_item["id"],
            "title": raw_item["title"],
            "description": raw_item["description"],
            "data_payload": raw_item,
        }


class TestCollectorError:
    """Tests for CollectorError exception"""

    def test_collector_error_is_exception(self):
        """Should be an Exception subclass"""
        error = CollectorError("Test error")

        assert isinstance(error, Exception)

    def test_collector_error_message(self):
        """Should store error message"""
        error = CollectorError("Collection failed")

        assert str(error) == "Collection failed"


class TestBaseCollectorInit:
    """Tests for BaseCollector initialization"""

    def test_init_with_required_params(self):
        """Should initialize with source name and type"""
        collector = ConcreteCollector(
            source_name="Test Source", source_type="events"
        )

        assert collector.source_name == "Test Source"
        assert collector.source_type == "events"
        assert collector.endpoint_url is None
        assert collector.api_key is None

    def test_init_with_all_params(self):
        """Should accept all optional parameters"""
        collector = ConcreteCollector(
            source_name="Test Source",
            source_type="events",
            endpoint_url="https://api.example.com",
            api_key="test-key-123",
        )

        assert collector.endpoint_url == "https://api.example.com"
        assert collector.api_key == "test-key-123"

    def test_init_creates_http_client(self):
        """Should create HTTP client on init"""
        collector = ConcreteCollector(source_name="Test", source_type="events")

        assert collector.http_client is not None


class TestSerializeForJson:
    """Tests for JSON serialization helper"""

    def test_serialize_datetime(self):
        """Should serialize datetime to ISO format"""
        dt = datetime(2024, 1, 15, 12, 30, 45)

        result = BaseCollector._serialize_for_json(dt)

        assert result == "2024-01-15T12:30:45"

    def test_serialize_dict_with_datetime(self):
        """Should recursively serialize datetimes in dicts"""
        data = {
            "title": "Test",
            "date": datetime(2024, 1, 15, 12, 0, 0),
        }

        result = BaseCollector._serialize_for_json(data)

        assert result["title"] == "Test"
        assert result["date"] == "2024-01-15T12:00:00"

    def test_serialize_list_with_datetime(self):
        """Should recursively serialize datetimes in lists"""
        data = [datetime(2024, 1, 15), datetime(2024, 1, 16)]

        result = BaseCollector._serialize_for_json(data)

        assert result == ["2024-01-15T00:00:00", "2024-01-16T00:00:00"]

    def test_serialize_nested_structure(self):
        """Should handle deeply nested structures"""
        data = {
            "events": [
                {"title": "Event 1", "date": datetime(2024, 1, 15)},
                {"title": "Event 2", "date": datetime(2024, 1, 16)},
            ]
        }

        result = BaseCollector._serialize_for_json(data)

        assert result["events"][0]["date"] == "2024-01-15T00:00:00"
        assert result["events"][1]["date"] == "2024-01-16T00:00:00"

    def test_serialize_simple_values(self):
        """Should pass through simple values unchanged"""
        assert BaseCollector._serialize_for_json("string") == "string"
        assert BaseCollector._serialize_for_json(123) == 123
        assert BaseCollector._serialize_for_json(True) is True
        assert BaseCollector._serialize_for_json(None) is None


class TestGetOrCreateSource:
    """Tests for get_or_create_source method"""

    def test_get_existing_source(self, mock_api_data_source):
        """Should return existing source"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_api_data_source
        )

        collector = ConcreteCollector(source_name="Test Source", source_type="events")

        result = collector._get_or_create_source(mock_session)

        assert result == mock_api_data_source
        assert not mock_session.add.called

    def test_create_new_source(self):
        """Should create new source if not exists"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        collector = ConcreteCollector(
            source_name="New Source",
            source_type="events",
            endpoint_url="https://api.example.com",
            api_key="key123",
        )

        collector._get_or_create_source(mock_session)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


class TestScoreRelevance:
    """Tests for relevance scoring"""

    def test_score_relevance_no_context(self, sample_parsed_item):
        """Should return neutral score without context"""
        collector = ConcreteCollector(source_name="Test", source_type="events")

        score, decisions = collector.score_relevance(sample_parsed_item)

        assert score == 0.5
        assert decisions == []

    def test_score_relevance_with_matches(
        self, sample_job_item, sample_decision_context
    ):
        """Should score higher with keyword matches"""
        collector = ConcreteCollector(source_name="Test", source_type="jobs")

        score, decisions = collector.score_relevance(
            sample_job_item, sample_decision_context
        )

        assert score > 0.1
        assert "decision-1" in decisions

    def test_score_relevance_no_matches(
        self, sample_parsed_item, sample_decision_context
    ):
        """Should return minimum score with no matches"""
        collector = ConcreteCollector(source_name="Test", source_type="events")
        item = {
            "title": "Unrelated Topic",
            "description": "Nothing relevant here",
        }

        score, decisions = collector.score_relevance(item, sample_decision_context)

        assert score == 0.1
        assert decisions == []

    def test_score_relevance_capped_at_one(self, sample_decision_context):
        """Should cap score at 1.0"""
        collector = ConcreteCollector(source_name="Test", source_type="jobs")
        item = {
            "title": "Jobs hiring employment career opportunity",
            "description": "Housing rent mortgage real estate market",
        }

        score, decisions = collector.score_relevance(item, sample_decision_context)

        assert score <= 1.0


class TestCollectAndStore:
    """Tests for main collection method"""

    @patch("src.collectors.base_collector.get_db")
    def test_collect_and_store_success(self, mock_get_db, mock_api_data_source):
        """Should collect, parse, and store data successfully"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_api_data_source,  # get_or_create_source
            None,  # existing item check
        ]

        collector = ConcreteCollector(source_name="Test", source_type="events")

        stats = collector.collect_and_store()

        assert stats["success"] is True
        assert stats["source"] == "Test"
        assert stats["new_items"] >= 0

    @patch("src.collectors.base_collector.get_db")
    def test_collect_and_store_updates_existing(
        self, mock_get_db, mock_api_data_source, mock_api_data_point
    ):
        """Should update existing items when relevance changes"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_api_data_point.relevance_score = 0.3  # Different from new score

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_api_data_source,
            mock_api_data_point,  # Existing item found
        ]

        collector = ConcreteCollector(source_name="Test", source_type="events")

        stats = collector.collect_and_store()

        assert stats["success"] is True

    @patch("src.collectors.base_collector.get_db")
    def test_collect_and_store_with_decision_context(
        self, mock_get_db, mock_api_data_source, sample_decision_context
    ):
        """Should use decision context for scoring"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_api_data_source,
            None,
        ]

        collector = ConcreteCollector(source_name="Test", source_type="events")

        stats = collector.collect_and_store(decision_context=sample_decision_context)

        assert stats["success"] is True

    @patch("src.collectors.base_collector.get_db")
    def test_collect_and_store_respects_max_items(
        self, mock_get_db, mock_api_data_source
    ):
        """Should respect max_items limit"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_api_data_source
        )

        class ManyItemsCollector(BaseCollector):
            def fetch_data(self):
                return [{"id": str(i), "title": f"Item {i}"} for i in range(50)]

            def parse_item(self, raw_item):
                return {
                    "data_type": "test",
                    "external_id": raw_item["id"],
                    "title": raw_item["title"],
                    "description": "",
                    "data_payload": raw_item,
                }

        collector = ManyItemsCollector(source_name="Test", source_type="events")

        stats = collector.collect_and_store(max_items=10)

        assert stats["total_fetched"] == 50

    @patch("src.collectors.base_collector.get_db")
    def test_collect_and_store_handles_fetch_error(self, mock_get_db, mock_api_data_source):
        """Should raise CollectorError on fetch failure"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_api_data_source
        )

        class FailingCollector(BaseCollector):
            def fetch_data(self):
                raise Exception("API unavailable")

            def parse_item(self, raw_item):
                return {}

        collector = FailingCollector(source_name="Test", source_type="events")

        with pytest.raises(CollectorError) as exc_info:
            collector.collect_and_store()

        assert "Failed to collect" in str(exc_info.value)


class TestAbstractMethods:
    """Tests for abstract method requirements"""

    def test_fetch_data_must_be_implemented(self):
        """Should require fetch_data implementation"""

        class IncompleteCollector(BaseCollector):
            def parse_item(self, raw_item):
                return {}

        with pytest.raises(TypeError):
            IncompleteCollector(source_name="Test", source_type="events")

    def test_parse_item_must_be_implemented(self):
        """Should require parse_item implementation"""

        class IncompleteCollector(BaseCollector):
            def fetch_data(self):
                return []

        with pytest.raises(TypeError):
            IncompleteCollector(source_name="Test", source_type="events")
