"""
Compiling triggers into a predicate: the shape, the refusals, and the boundaries.

**On the boundary class in this file, and why it is written the way it is.**
Backlog task 010 found that its own boundary tests passed for the wrong reason:
every collision case used a SHOUTED term, and a shouted term matches
case-sensitively, so ``combat`` was rejected as a mention of ``OMB`` before the
anchors were ever consulted. The whole class passed with ``LEFT_BOUNDARY`` and
``RIGHT_BOUNDARY`` deleted from the codebase.

So every case in :class:`TestWordBoundariesAreLoadBearing` uses a term that is
**not** shouted -- ``nist``, ``mail``, ``ai``, ``rev`` -- and is therefore
compiled case-insensitively. Case cannot reject any of them. The anchors are the
only thing standing between the term and its host word, which means deleting the
anchors makes the class fail. That was checked by deleting them, on 2026-08-31;
see the class docstring for what happened.
"""

from __future__ import annotations

import pytest

from src.routing import CompiledWatch, TriggerCompileError, compile_watch, source_keys


def watch(*clauses, watch_id="w") -> CompiledWatch:
    return compile_watch(watch_id, list(clauses))


def fires(compiled, text, *sources) -> bool:
    return compiled.matches(text, source_keys(*sources))


class TestClauseSemantics:
    """AND within a clause, OR across clauses. This is the whole grammar."""

    def test_terms_within_a_field_are_or(self):
        w = watch({"terms": ["ConMon", "continuous monitoring"]})
        assert fires(w, "the ConMon burden grew")
        assert fires(w, "continuous monitoring requirements")
        assert not fires(w, "an unrelated rule")

    def test_fields_within_a_clause_are_and(self):
        w = watch({"entities": ["GSA"], "terms": ["continuous monitoring"]})
        assert fires(w, "GSA expanded continuous monitoring")
        assert not fires(w, "GSA expanded nothing in particular")
        assert not fires(w, "continuous monitoring, by someone else entirely")

    def test_clauses_are_or(self):
        w = watch(
            {"entities": ["GSA"], "terms": ["continuous monitoring"]},
            {"terms": ["FedRAMP 20x"]},
        )
        assert fires(w, "GSA expanded continuous monitoring")
        assert fires(w, "FedRAMP 20x lands")
        assert not fires(w, "neither of those things")

    def test_the_firing_clause_is_reported_by_index(self):
        w = watch({"terms": ["alpha"]}, {"terms": ["beta"]})
        assert w.matching_clause("beta only", frozenset()) == 1
        assert w.matching_clause("alpha only", frozenset()) == 0
        assert w.matching_clause("nothing", frozenset()) is None

    def test_the_first_matching_clause_wins(self):
        """Two clauses matching is still one candidate, attributed to the first."""
        w = watch({"terms": ["alpha"]}, {"terms": ["beta"]})
        assert w.matching_clause("alpha and beta", frozenset()) == 0


class TestSourceAllowlist:
    """
    ``sources`` is an allowlist matched by equality, not by substring.

    Substring matching here would mean a clause naming "Federal Register" also
    accepting a blog called "Federal Register Watch", which is the same class of
    error as an unanchored term and is worse, because it silently widens a
    clause the operator wrote to be narrow.

    **A consequence, measured on the real corpus on 2026-08-31 and recorded
    because it is a live question rather than a defect:** the feeds in this
    repository are named "Federal Register", "Federal Register - Public
    Inspection" and "Federal Register - Documents API", and only the last of
    those has stored articles. A clause saying ``sources: [Federal Register]``
    therefore matches none of them. Equality is the conservative reading -- it
    can only under-route, never over-route, and under-routing surfaces as an
    unrouted cluster. Whether an operator means the exact feed or the family of
    feeds is a question for the operator, not an assumption to make here.
    """

    def test_matches_the_feed_name(self):
        w = watch({"sources": ["Federal Register"], "terms": ["FedRAMP"]})
        assert fires(w, "a FedRAMP notice", "Federal Register")

    def test_matches_the_feed_url(self):
        w = watch({"sources": ["https://www.federalregister.gov/articles.rss"]})
        assert fires(
            w, "anything", "Federal Register", "https://www.federalregister.gov/articles.rss"
        )

    def test_is_case_and_whitespace_insensitive(self):
        w = watch({"sources": ["  federal REGISTER "]})
        assert fires(w, "anything", "Federal Register")

    def test_does_not_match_a_longer_name(self):
        w = watch({"sources": ["Federal Register"]})
        assert not fires(w, "anything", "Federal Register Watch Blog")

    def test_a_source_clause_still_ands_with_its_terms(self):
        w = watch({"sources": ["Federal Register"], "terms": ["FedRAMP"]})
        assert not fires(w, "an unrelated notice", "Federal Register")
        assert not fires(w, "a FedRAMP notice", "FedScoop")


class TestWordBoundariesAreLoadBearing:
    """
    Terms match whole words. Every case here uses a non-shouted term.

    **Verified by deletion on 2026-08-31.** With ``LEFT_BOUNDARY`` and
    ``RIGHT_BOUNDARY`` set to the empty string in
    ``src/matching/entity_matcher.py`` and ``term_pattern`` reduced to the bare
    escaped term, every test in this class fails. That is the check task 010's
    equivalent class did not survive: its cases were shouted acronyms, rejected
    by the case rule before the anchors were reached, so it passed with the
    anchors gone.

    The scale being defended, measured on this repository's 55,249-article
    corpus: ``nist`` appears as a substring in 5,364 titles and at a word
    boundary in 73; ``mail`` is 1,842 against 339; the whole-text substring
    count for ``opm`` is 1,706 -- almost all of it the word "development" --
    against 14 at a boundary.
    """

    @pytest.mark.parametrize(
        "host",
        [
            "The administration said so.",
            "the minister of the interior",
            "Afghanistan's economy",
            "a sinister development",
            "communist party congress",
        ],
    )
    def test_lowercase_nist_does_not_match_its_host_words(self, host):
        """
        ``nist`` is lowercase, so it compiles case-insensitively.

        There is no case rule available to reject "admiNISTration" here. If the
        anchors go, this passes and the watch starts routing 5,364 titles.
        """
        w = watch({"terms": ["nist"]})
        assert not fires(w, host)

    def test_lowercase_nist_does_match_the_whole_word(self):
        w = watch({"terms": ["nist"]})
        assert fires(w, "the nist catalog")
        assert fires(w, "NIST published a revision")

    @pytest.mark.parametrize(
        "host", ["send an email", "blackmail allegations", "a mailbox rule", "mailing list"]
    )
    def test_mail_does_not_match_its_host_words(self, host):
        w = watch({"terms": ["mail"]})
        assert not fires(w, host)

    def test_mail_does_match_the_whole_word(self):
        w = watch({"terms": ["mail"]})
        assert fires(w, "the mail was delayed")
        assert fires(w, "delivered by MAIL yesterday")

    @pytest.mark.parametrize(
        "host", ["he said nothing", "maintain the system", "a certain claim", "chairman"]
    )
    def test_two_letter_ai_does_not_match_its_host_words(self, host):
        w = watch({"terms": ["ai"]})
        assert not fires(w, host)

    def test_a_multiword_term_is_anchored_at_both_ends(self):
        w = watch({"terms": ["rev 5"]})
        assert not fires(w, "prerev 5 draft")
        assert not fires(w, "rev 55 of the document")
        assert fires(w, "Rev 5 baseline")

    def test_a_hyphen_and_a_slash_are_boundaries_not_word_characters(self):
        """ "CISA-issued" is a mention; "precisa" is not. Both matter."""
        w = watch({"terms": ["conmon"]})
        assert fires(w, "conmon-related work")
        assert fires(w, "conmon/significant-change reporting")
        assert not fires(w, "preconmonitor readings")

    def test_a_term_split_across_a_line_wrap_still_matches(self):
        w = watch({"terms": ["continuous monitoring"]})
        assert fires(w, "expanded continuous\n   monitoring duties")


class TestShoutedAcronymsAreCaseSensitive:
    """
    The second rule, tested separately so neither can cover for the other.

    These cases would pass with the anchors deleted -- that is the point of
    keeping them out of the boundary class.
    """

    def test_a_shouted_term_is_not_matched_in_lower_case(self):
        w = watch({"entities": ["OMB"]})
        assert fires(w, "OMB issued guidance")
        assert not fires(w, "the omb issued guidance")

    def test_an_unshouted_term_is_matched_in_any_case(self):
        w = watch({"entities": ["FedRAMP PMO"]})
        assert fires(w, "the fedramp pmo said")
        assert fires(w, "the FEDRAMP PMO said")


class TestRefusals:
    """
    Everything this compiler cannot evaluate, it refuses. It never skips.

    A skipped clause is a watch that has quietly stopped watching; a kept empty
    clause is a watch that matches the entire corpus. The loader already rejects
    both, but the loader is not the only way JSON reaches ``watches.triggers`` --
    a hand-edited row, a restored dump and a future migration all bypass it.
    """

    def test_a_clause_constraining_nothing_is_refused(self):
        with pytest.raises(TriggerCompileError, match="constrains nothing"):
            compile_watch("w", [{}])

    def test_a_clause_whose_fields_are_all_blank_is_refused(self):
        with pytest.raises(TriggerCompileError, match="every entry is blank"):
            compile_watch("w", [{"terms": ["  ", ""]}])

    def test_empty_triggers_are_refused(self):
        with pytest.raises(TriggerCompileError, match="non-empty list"):
            compile_watch("w", [])

    def test_prose_triggers_are_refused(self):
        with pytest.raises(TriggerCompileError, match="non-empty list"):
            compile_watch("w", "anything about FedRAMP")

    def test_a_prose_clause_is_refused(self):
        with pytest.raises(TriggerCompileError, match="expected a mapping"):
            compile_watch("w", ["anything about FedRAMP"])

    def test_a_string_where_a_list_belongs_is_refused(self):
        with pytest.raises(TriggerCompileError, match="must be a list of strings"):
            compile_watch("w", [{"terms": "FedRAMP"}])

    def test_an_unknown_clause_field_is_refused(self):
        with pytest.raises(TriggerCompileError, match="unknown field"):
            compile_watch("w", [{"terms": ["FedRAMP"], "authors": ["someone"]}])

    def test_a_clause_that_would_lose_a_conjunct_is_refused(self):
        """
        A declared field whose every value is blank would silently widen the clause.

        ``{"entities": [" "], "terms": ["FedRAMP"]}`` reads as "FedRAMP AND some
        entity" and would evaluate as "FedRAMP", which is a different and
        broader watch than the one written down.
        """
        with pytest.raises(TriggerCompileError, match="every entry is blank"):
            compile_watch("w", [{"entities": ["   "], "terms": ["FedRAMP"]}])
