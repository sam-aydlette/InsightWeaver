"""Tests for the shared Claude JSON parser."""

from src.context._json import parse_claude_json


def test_parses_valid_json():
    assert parse_claude_json('{"clusters": [{"title": "Test"}]}') == {
        "clusters": [{"title": "Test"}]
    }


def test_strips_markdown_fences():
    assert parse_claude_json('```json\n{"key": "value"}\n```') == {"key": "value"}


def test_strips_bare_fences():
    assert parse_claude_json('```\n{"key": "value"}\n```') == {"key": "value"}


def test_returns_empty_dict_on_invalid_json():
    assert parse_claude_json("This is not JSON") == {}
