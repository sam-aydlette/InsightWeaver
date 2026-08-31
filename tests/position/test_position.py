"""
Tests for the Position loader (backlog task 013).

The split these tests are written against: structural problems are rejections,
judgement calls are warnings. A decision with no deadline cannot be repaired by
the loader and is refused; a Position that has grown to three pages might be
exactly right and is only named.
"""

from datetime import date
from pathlib import Path

import pytest

from src.position import MAX_PAGES, POSITION_PAGE_WORDS, Position, PositionError, load_position

from .conftest import TODAY

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "position.example.yaml"


class TestLoadsValidPosition:
    def test_loads_decisions(self, position):
        assert isinstance(position, Position)
        assert position.decision_keys == {"renew-authorization", "hire-engineer"}

    def test_decision_lookup(self, position):
        found = position.decision("hire-engineer")
        assert found is not None
        assert found.deadline == date(2026, 12, 15)
        assert found.days_remaining(TODAY) == 105

    def test_unknown_decision_lookup_returns_none(self, position):
        assert position.decision("not-a-decision") is None

    def test_reviewed_date(self, position):
        assert position.reviewed == date(2026, 8, 31)

    def test_valid_position_warns_about_nothing(self, position):
        assert position.warnings == ()


class TestCheckedInExample:
    """
    The example in this repo has to actually load.

    An example file that does not parse is worse than no example: it is the
    first thing a new operator copies.
    """

    def test_example_loads(self):
        loaded = load_position(EXAMPLE, today=TODAY)
        assert len(loaded.decisions) == 3
        assert all(d.deadline > TODAY for d in loaded.decisions)

    def test_example_is_under_two_pages(self):
        loaded = load_position(EXAMPLE, today=TODAY)
        assert loaded.word_count <= POSITION_PAGE_WORDS * MAX_PAGES
        assert loaded.warnings == ()


class TestMissingFile:
    def test_absent_position_fails_fast(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc:
            load_position(tmp_path / "nope.yaml")
        assert "POSITION_PATH" in str(exc.value)

    def test_error_points_at_the_example(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc:
            load_position(tmp_path / "nope.yaml")
        assert "position.example.yaml" in str(exc.value)


class TestRejections:
    def test_decision_without_deadline_is_rejected(self, write_yaml, position_doc):
        del position_doc["decisions"][0]["deadline"]
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError) as exc:
            load_position(path, today=TODAY)
        assert "'deadline' is required" in str(exc.value)

    def test_deadline_that_is_not_a_date_is_rejected(self, write_yaml, position_doc):
        position_doc["decisions"][0]["deadline"] = "when the budget lands"
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError, match="is not a date"):
            load_position(path, today=TODAY)

    def test_missing_name_is_rejected(self, write_yaml, position_doc):
        position_doc["decisions"][1]["name"] = "   "
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError, match="'name' is required"):
            load_position(path, today=TODAY)

    def test_duplicate_keys_are_rejected(self, write_yaml, position_doc):
        position_doc["decisions"][1]["key"] = "renew-authorization"
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError, match="duplicate decision key"):
            load_position(path, today=TODAY)

    def test_non_slug_key_is_rejected(self, write_yaml, position_doc):
        position_doc["decisions"][0]["key"] = "Renew The Authorization"
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError, match="is not a slug"):
            load_position(path, today=TODAY)

    def test_empty_decisions_is_rejected(self, write_yaml, position_doc):
        position_doc["decisions"] = []
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError, match="holds no stakes"):
            load_position(path, today=TODAY)

    def test_unknown_field_is_rejected(self, write_yaml, position_doc):
        position_doc["decisions"][0]["urgency"] = "high"
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError, match="unknown field"):
            load_position(path, today=TODAY)

    def test_empty_file_is_rejected(self, write_yaml):
        path = write_yaml("position.yaml", "# nothing but a comment\n")
        with pytest.raises(PositionError, match="empty"):
            load_position(path, today=TODAY)

    def test_malformed_yaml_is_rejected(self, write_yaml):
        path = write_yaml("position.yaml", "decisions: [\n  - key: x\n")
        with pytest.raises(PositionError, match="not valid YAML"):
            load_position(path, today=TODAY)

    def test_every_problem_is_reported_at_once(self, write_yaml, position_doc):
        del position_doc["decisions"][0]["deadline"]
        position_doc["decisions"][1]["name"] = ""
        path = write_yaml("position.yaml", position_doc)
        with pytest.raises(PositionError) as exc:
            load_position(path, today=TODAY)
        assert len(exc.value.problems) == 2


class TestWarnsRatherThanFails:
    def test_long_position_warns_and_still_loads(self, write_yaml, position_doc):
        """
        Over two pages the loader names the drift. It does not refuse.

        A three-page Position of genuine deadlines beats a one-page Position of
        vague interests, so length can only ever be a flag.
        """
        filler = " ".join(["exposure"] * (POSITION_PAGE_WORDS * MAX_PAGES + 50))
        position_doc["decisions"][0]["stake"] = filler
        path = write_yaml("position.yaml", position_doc)

        loaded = load_position(path, today=TODAY)

        assert loaded.word_count > POSITION_PAGE_WORDS * MAX_PAGES
        assert len(loaded.decisions) == 2
        assert any("interests" in note for note in loaded.warnings)
        assert any("pages" in note for note in loaded.warnings)

    def test_warning_is_logged_loudly(self, write_yaml, position_doc, caplog):
        filler = " ".join(["exposure"] * (POSITION_PAGE_WORDS * MAX_PAGES + 50))
        position_doc["decisions"][0]["stake"] = filler
        path = write_yaml("position.yaml", position_doc)

        with caplog.at_level("WARNING", logger="src.position.position"):
            load_position(path, today=TODAY)

        assert any("interests" in record.message for record in caplog.records)

    def test_comments_do_not_count_towards_the_page_limit(self, write_yaml, position_doc):
        """
        The operator's notes are not drift.

        Counting comments would make the warning fire on a well-annotated file,
        which is the opposite of what it is for.
        """
        comment = "\n".join(["# " + " ".join(["note"] * 20)] * 60)
        path = write_yaml("position.yaml", position_doc)
        path.write_text(comment + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8")

        loaded = load_position(path, today=TODAY)

        assert loaded.warnings == ()

    def test_past_deadline_warns(self, write_yaml, position_doc):
        position_doc["decisions"][0]["deadline"] = date(2026, 1, 1)
        path = write_yaml("position.yaml", position_doc)

        loaded = load_position(path, today=TODAY)

        assert len(loaded.decisions) == 2
        assert any("passed its deadline" in note for note in loaded.warnings)

    def test_missing_stake_warns(self, write_yaml, position_doc):
        del position_doc["decisions"][0]["stake"]
        path = write_yaml("position.yaml", position_doc)

        loaded = load_position(path, today=TODAY)

        assert any("states no 'stake'" in note for note in loaded.warnings)
