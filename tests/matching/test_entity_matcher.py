"""
Tests for deterministic coverage-entity matching.

The point of interest is the collision surface. Federal acronyms are short and
sit inside ordinary words: `CISA` inside "precisa", `OMB` inside "bombing" and
"combat", `BOD` inside "body", `SRG` inside a URL slug. A substring matcher
would report institutional activity on a Portuguese sentence about scheduling.
Every one of those is pinned below.

No fixture here names a natural person, and none can: the matcher only accepts
CoverageEntity values, whose kind is org / program / document_type.
"""

from src.matching.entity_matcher import (
    compile_entities,
    count_item_mentions,
    item_text,
)
from src.matching.terms import CoverageEntity


def counts(entities, texts):
    """Mention counts keyed by canonical name, for readable assertions."""
    by_key = count_item_mentions(compile_entities(entities), texts)
    return {entity.name: by_key[entity.key] for entity in entities}


CISA = CoverageEntity("org", "CISA", ("Cybersecurity and Infrastructure Security Agency",))
OMB = CoverageEntity("org", "OMB", ("Office of Management and Budget",))
GSA = CoverageEntity("org", "GSA")
PMO = CoverageEntity("org", "FedRAMP PMO", ("FedRAMP Program Management Office",))
CMMC = CoverageEntity("program", "CMMC")
TWENTY_X = CoverageEntity("program", "FedRAMP 20x")
TX_RAMP = CoverageEntity("program", "TX-RAMP")
BOD = CoverageEntity("document_type", "Binding Operational Directive", ("BOD",))


class TestAliasMatching:
    def test_canonical_name_matches(self):
        assert counts([CISA], ["CISA published an advisory."]) == {"CISA": 1}

    def test_alias_matches(self):
        text = "The Cybersecurity and Infrastructure Security Agency published an advisory."
        assert counts([CISA], [text]) == {"CISA": 1}

    def test_an_item_naming_the_entity_twice_counts_once(self):
        """
        Items, not occurrences. Counting repetitions would let one verbose
        outlet impersonate a busy agency.
        """
        text = "CISA said. CISA also said. The Cybersecurity and Infrastructure Security Agency."
        assert counts([CISA], [text]) == {"CISA": 1}

    def test_counts_are_per_item_across_items(self):
        assert counts([CISA], ["CISA acted.", "Nothing here.", "CISA again."]) == {"CISA": 2}

    def test_multiword_name_tolerates_a_line_wrap(self):
        """Source text arrives wrapped; a name split across lines is still the name."""
        assert counts([PMO], ["The FedRAMP\n  PMO issued guidance."]) == {"FedRAMP PMO": 1}

    def test_multiword_name_does_not_match_out_of_order(self):
        assert counts([PMO], ["PMO of FedRAMP"]) == {"FedRAMP PMO": 0}

    def test_mixed_case_names_match_case_insensitively(self):
        """Ordinary names are case-varied in prose and long enough not to collide."""
        assert counts([PMO], ["the fedramp pmo said"]) == {"FedRAMP PMO": 1}

    def test_a_declared_entity_with_no_mention_still_gets_a_zero(self):
        """
        A zero is an observation. Dropping the key here would make "never
        mentioned" and "never looked for" indistinguishable downstream.
        """
        assert counts([CISA, OMB], ["CISA acted."]) == {"CISA": 1, "OMB": 0}

    def test_no_items_yields_zeroes_not_an_empty_result(self):
        assert counts([CISA, CMMC], []) == {"CISA": 0, "CMMC": 0}


class TestAcronymCollisions:
    """
    The named landmines. Each of these strings contains the acronym as a
    substring and must not count as a mention.
    """

    def test_cisa_inside_precisa(self):
        assert counts([CISA], ["A agenda precisa de mais tempo."]) == {"CISA": 0}

    def test_cisa_inside_other_tokens(self):
        text = "A decisa ruling, an imprecisa figure, and the CISAX vendor."
        assert counts([CISA], [text]) == {"CISA": 0}

    def test_omb_inside_bombing_combat_and_tomb(self):
        text = "The bombing followed combat near the tomb; comb through the record."
        assert counts([OMB], [text]) == {"OMB": 0}

    def test_bod_inside_body_and_everybody(self):
        text = "The body of the rule; everybody agrees; embodied guidance."
        assert counts([BOD], [text]) == {"Binding Operational Directive": 0}

    def test_nist_inside_administration_minister_and_afghanistan(self):
        """
        Measured against the real corpus on 2026-08-26: of 50,983 stored
        articles, 617 had "nist" somewhere in the title and exactly 2 were
        about NIST. The rest were "administration" (329), "minister" (154),
        "Afghanistan" (40), "communist", "sinister". A substring matcher would
        have reported NIST as the most active institution in the country,
        every day, forever.
        """
        nist = CoverageEntity("org", "NIST")
        text = (
            "The administration's minister said Afghanistan's communist past "
            "was a sinister administrative matter."
        )
        assert counts([nist], [text]) == {"NIST": 0}
        assert counts([nist], ["NIST published SP 800-53 revision 6."]) == {"NIST": 1}

    def test_gsa_inside_a_longer_token(self):
        assert counts([GSA], ["Contact gsanders@example.gov or see GSAdvantage."]) == {"GSA": 0}

    def test_cmmc_inside_a_url_slug(self):
        assert counts([CMMC], ["https://example.gov/aboutcmmcprogram/index.html"]) == {"CMMC": 0}

    def test_lowercase_acronym_is_not_a_mention(self):
        """
        An all-capitals term is an acronym, and an acronym is only itself when
        it is shouted. This is what keeps "combat" from becoming OMB even if a
        boundary rule were ever loosened, and "bod" from becoming a directive.
        """
        assert counts([OMB, BOD, GSA], ["the omb and the bod and the gsa"]) == {
            "OMB": 0,
            "Binding Operational Directive": 0,
            "GSA": 0,
        }

    def test_the_acronym_itself_still_matches_when_shouted(self):
        assert counts([OMB, BOD, GSA], ["OMB, BOD 25-01 and GSA"]) == {
            "OMB": 1,
            "Binding Operational Directive": 1,
            "GSA": 1,
        }

    def test_mixed_case_alias_of_a_shouted_entity_still_matches_relaxed(self):
        """
        The case rule is per surface form, not per entity: `BOD` is strict,
        `Binding Operational Directive` is not.
        """
        assert counts([BOD], ["a binding operational directive lands"]) == {
            "Binding Operational Directive": 1
        }


class TestBoundaryCharacters:
    def test_hyphen_and_slash_are_boundaries_not_word_characters(self):
        """
        "CISA-issued" is a mention of CISA. Requiring whitespace on both sides
        would silently miss most headline usage.
        """
        assert counts([CISA], ["A CISA-issued advisory.", "A FedRAMP/CISA joint note."]) == {
            "CISA": 2
        }

    def test_punctuation_around_a_name_does_not_block_it(self):
        assert counts([CISA], ['("CISA"), the agency,']) == {"CISA": 1}

    def test_a_hyphenated_entity_name_matches_verbatim(self):
        assert counts([TX_RAMP], ["TX-RAMP certification opens."]) == {"TX-RAMP": 1}

    def test_a_hyphenated_entity_name_does_not_match_its_tail(self):
        assert counts([TX_RAMP], ["StateRAMP and RAMP generally."]) == {"TX-RAMP": 0}

    def test_a_name_ending_in_a_digit_token_matches(self):
        assert counts([TWENTY_X], ["FedRAMP 20x pilot expands."]) == {"FedRAMP 20x": 1}

    def test_a_name_ending_in_a_digit_token_is_not_a_prefix_match(self):
        assert counts([TWENTY_X], ["FedRAMP 20xtreme"]) == {"FedRAMP 20x": 0}


class TestItemText:
    def test_title_and_content_are_both_searched(self):
        assert counts([CISA], [item_text({"title": "CISA acts", "content": ""})]) == {"CISA": 1}
        assert counts([CISA], [item_text({"title": "", "content": "CISA acts"})]) == {"CISA": 1}

    def test_missing_fields_do_not_raise(self):
        assert item_text({}) == "\n"

    def test_the_author_field_is_not_searched(self):
        """
        A byline is a person. Feeding it to a counter that accumulates across
        runs is precisely the design this feature exists not to be.
        """
        text = item_text({"title": "Rule lands", "content": "Body", "author": "CISA"})
        assert counts([CISA], [text]) == {"CISA": 0}


class TestDeterminism:
    def test_the_same_input_always_produces_the_same_counts(self):
        texts = ["CISA and OMB acted.", "The FedRAMP PMO was quiet."]
        entities = [CISA, OMB, PMO, CMMC]

        first = counts(entities, texts)
        second = counts(entities, texts)

        assert first == second
        assert first == {"CISA": 1, "OMB": 1, "FedRAMP PMO": 1, "CMMC": 0}
