"""
Tests for BriefDocument -- the model the renderers share.
"""

import pytest

from src.render.document import BriefDocument, StoredBriefNotFound

from .conftest import SYNTHESIS_DATA


class TestFromSynthesisData:
    def test_pulls_every_section(self, brief_document):
        assert len(brief_document.situations) == 2
        assert len(brief_document.thin_coverage) == 1
        assert len(brief_document.meta_fractures) == 1
        assert brief_document.metadata["analysis_threshold"] == "2+ articles"

    def test_carries_provenance(self, brief_document):
        assert brief_document.synthesis_id == 176
        assert brief_document.analysis_run_id == 15
        assert brief_document.articles_analyzed == 42

    def test_handles_none_payload(self):
        doc = BriefDocument.from_synthesis_data(None)
        assert doc.situations == []
        assert doc.metadata == {}
        assert doc.is_empty()

    def test_drops_non_dict_entries(self):
        doc = BriefDocument.from_synthesis_data(
            {"situations": ["not a situation", {"title": "ok"}]}
        )
        assert doc.situations == [{"title": "ok"}]

    def test_falls_back_to_metadata_article_count(self):
        doc = BriefDocument.from_synthesis_data({"metadata": {"articles_analyzed": 9}})
        assert doc.articles_analyzed == 9

    def test_is_empty_is_false_when_any_section_present(self, brief_document):
        assert not brief_document.is_empty()


class TestFromReport:
    def test_reads_the_legacy_pipeline_shape(self):
        report = {
            "success": True,
            "articles_analyzed": 7,
            "synthesis_data": SYNTHESIS_DATA,
            "synthesis_id": 176,
        }
        doc = BriefDocument.from_report(report)
        assert doc.articles_analyzed == 7  # run count wins over the metadata count
        assert doc.metadata_articles_analyzed == 42
        assert doc.synthesis_id == 176
        assert len(doc.situations) == 2

    def test_handles_missing_report(self):
        assert BriefDocument.from_report(None).is_empty()

    def test_round_trips_back_to_report_shape(self, brief_document):
        report = brief_document.to_report()
        assert report["synthesis_data"] == BriefDocument.from_report(report).synthesis_data


class TestNamedViews:
    def test_decisions(self, brief_document):
        assert brief_document.decisions[0]["decision"] == "Whether to bid on the follow-on"

    def test_prediction_check(self, brief_document):
        assert brief_document.prediction_check["checked"] == 4

    def test_cluster_counts(self, brief_document):
        assert brief_document.clusters_analyzed == 2
        assert brief_document.clusters_thin == 1
        assert brief_document.clusters_total == 5

    def test_threshold_default(self):
        assert BriefDocument().analysis_threshold == "3+ articles"

    def test_counts_coerce_bad_types_to_zero(self):
        doc = BriefDocument.from_synthesis_data({"metadata": {"clusters_total": "many"}})
        assert doc.clusters_total == 0


class TestQuestions:
    def test_collects_primary_and_secondary_in_order(self, brief_document):
        questions = brief_document.questions
        assert [q["role"] for q in questions] == ["primary", "secondary", "secondary"]
        assert questions[0]["text"] == "Will the protest be sustained?"
        assert questions[0]["question_id"] == 7
        assert questions[1]["text"] == "Who audits the waiver?"
        assert questions[2]["text"] == "A bare legacy string question"

    def test_tags_the_source_situation(self, brief_document):
        assert {q["situation_index"] for q in brief_document.questions} == {1}

    def test_supports_the_legacy_single_string_shape(self):
        doc = BriefDocument.from_synthesis_data(
            {"situations": [{"where_this_goes": {"unresolved_question": "Legacy?"}}]}
        )
        assert doc.questions == [{"situation_index": 1, "role": "primary", "text": "Legacy?"}]

    def test_skips_situations_without_questions(self, brief_document):
        # The second fixture situation has no where_this_goes block at all.
        assert all(q["situation_index"] == 1 for q in brief_document.questions)


class TestDateStamp:
    def test_uses_stored_provenance_not_the_clock(self, brief_document):
        assert brief_document.date_stamp == "2026-05-15"

    def test_falls_back_to_metadata(self):
        doc = BriefDocument.from_synthesis_data({"metadata": {"generated_at": "2026-01-02 03:04"}})
        assert doc.date_stamp == "2026-01-02"

    def test_empty_when_unknown(self):
        assert BriefDocument().date_stamp == ""


class TestStoredBriefNotFound:
    def test_message_lists_available_ids(self):
        exc = StoredBriefNotFound(999, [189, 188, 176])
        assert "999" in str(exc)
        assert "189, 188, 176" in str(exc)

    def test_message_when_nothing_stored(self):
        assert "none" in str(StoredBriefNotFound(1, []))

    def test_is_a_lookup_error(self):
        with pytest.raises(LookupError):
            raise StoredBriefNotFound(1, [])


class TestStandingAgendaView:
    """The named view the renderers read the declared agenda through."""

    def test_absent_by_default(self, brief_document):
        assert brief_document.standing_agenda == []

    def test_carries_every_entry_including_unmoved(self, beat_document):
        agenda = beat_document.standing_agenda
        assert len(agenda) == 3
        assert [entry["moved"] for entry in agenda] == [True, False, False]

    def test_survives_a_payload_round_trip(self, beat_document):
        """This is what makes --from-run replay the same agenda the run reported."""
        replayed = BriefDocument.from_synthesis_data(beat_document.synthesis_data)
        assert replayed.standing_agenda == beat_document.standing_agenda

    def test_ignores_a_malformed_payload(self, brief_document):
        doc = BriefDocument.from_synthesis_data({"metadata": {"standing_agenda": "not a list"}})
        assert doc.standing_agenda == []
