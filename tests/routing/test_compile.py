"""
Trigger clause semantics, as the watch file promises them.

AND across a clause's populated fields, OR within a field, any clause fires
the watch, word boundaries and the shouted-term case rule throughout. Every
test here is a sentence from ``config/watches.example.yaml``'s comment block
turned into an assertion.
"""

import pytest

from src.routing import TriggerCompileError, compile_triggers


def first(triggers, text, source="Any Source"):
    return compile_triggers("w", triggers).first_match(text, source)


class TestFieldSemantics:
    def test_any_term_in_a_field_matches(self):
        clauses = [{"terms": ["continuous monitoring", "ConMon"]}]
        assert first(clauses, "The ConMon scope grew.") == 0
        assert first(clauses, "Continuous monitoring expanded.") == 0

    def test_every_populated_field_in_a_clause_must_match(self):
        clauses = [{"entities": ["FedRAMP PMO"], "terms": ["continuous monitoring"]}]
        assert first(clauses, "FedRAMP PMO expanded continuous monitoring.") == 0
        assert first(clauses, "FedRAMP PMO published guidance.") is None
        assert first(clauses, "Continuous monitoring is hard.") is None

    def test_any_clause_fires_and_the_first_is_recorded(self):
        clauses = [
            {"terms": ["Rev 5"]},
            {"sources": ["Federal Register"], "terms": ["FedRAMP"]},
        ]
        assert first(clauses, "FedRAMP notice", source="Federal Register") == 1
        assert first(clauses, "Rev 5 and FedRAMP", source="Federal Register") == 0

    def test_sources_match_the_name_case_insensitively_and_exactly(self):
        clauses = [{"sources": ["Federal Register"], "terms": ["FedRAMP"]}]
        assert first(clauses, "FedRAMP", source="federal register") == 0
        assert first(clauses, "FedRAMP", source="Federal Register - Documents API") is None

    def test_a_sources_only_clause_routes_everything_from_that_source(self):
        clauses = [{"sources": ["Federal Register"]}]
        assert first(clauses, "anything at all", source="Federal Register") == 0
        assert first(clauses, "anything at all", source="AP") is None


class TestBoundariesAndCase:
    """
    The two rules that cost a day to find. Word boundaries: of 55,249
    articles, 5,364 contained the substring ``nist`` and 73 matched at a word
    boundary. Case: ``BOD`` is a directive; ``body`` is not.
    """

    def test_a_term_inside_a_longer_word_does_not_match(self):
        assert first([{"terms": ["CISA"]}], "precisa") is None
        assert first([{"terms": ["NIST"]}], "the administration said") is None
        assert first([{"terms": ["CISA"]}], "CISA-issued directive") == 0

    def test_a_shouted_term_is_case_sensitive(self):
        assert first([{"entities": ["BOD"]}], "the body politic") is None
        assert first([{"entities": ["BOD"]}], "BOD 23-01") == 0
        assert first([{"terms": ["OMB"]}], "combat readiness") is None

    def test_a_mixed_case_term_is_case_insensitive(self):
        assert first([{"terms": ["FedRAMP"]}], "FEDRAMP marketplace") == 0
        assert first([{"terms": ["continuous monitoring"]}], "CONTINUOUS MONITORING") == 0

    def test_whitespace_inside_a_term_survives_a_line_wrap(self):
        assert first([{"terms": ["continuous monitoring"]}], "continuous\nmonitoring") == 0

    def test_entities_compile_exactly_as_terms_do(self):
        as_term = compile_triggers("a", [{"terms": ["FedRAMP PMO"]}])
        as_entity = compile_triggers("b", [{"entities": ["FedRAMP PMO"]}])
        for text in ("fedramp pmo said", "the FedRAMP PMO", "FedRAMP PMOs"):
            assert (as_term.first_match(text, "s") is None) == (
                as_entity.first_match(text, "s") is None
            )


class TestRefusal:
    """A stored row can be written by hand; the compiler refuses what the loader would."""

    @pytest.mark.parametrize(
        "triggers",
        [
            None,
            [],
            [{}],
            [{"terms": []}],
            [{"terms": "a sentence, not a list"}],
            [{"topic": ["unknown field"]}],
            ["prose clause"],
        ],
    )
    def test_uncompilable_triggers_raise(self, triggers):
        with pytest.raises(TriggerCompileError):
            compile_triggers("w", triggers)

    def test_the_error_names_the_watch_and_the_clause(self):
        with pytest.raises(TriggerCompileError, match=r"watch 'w' clause 1"):
            compile_triggers("w", [{"terms": ["ok"]}, {"nope": ["x"]}])
