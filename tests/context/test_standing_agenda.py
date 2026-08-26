"""
Tests for declared standing questions.

The first class here is the one that matters. A standing question exists so
that "nothing moved on this" can be said out loud; a standing question that
disappears on a quiet day is the failure this whole feature exists to prevent.
So the no-movement path is pinned before anything else, and it is pinned at
every layer it passes through: the agenda builder, the stored payload, and
each renderer.

Everything runs against the per-test SQLite file from ``test_engine``. Nothing
touches the configured DATABASE_URL, the network, or Claude.
"""

from datetime import datetime, timedelta

import pytest

from src.context.beat_scope import (
    ensure_beat,
    owning_beat_names,
    question_scope_filter,
    scoped_appearance_count,
)
from src.context.standing_agenda import build_standing_agenda, seed_standing_questions
from src.database.models import (
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    QUESTION_STATUS_OPEN,
    QUESTION_STATUS_RESOLVED,
    AnalysisRun,
    BeatRun,
    BeatStandingQuestion,
    NarrativeSynthesis,
    Prediction,
    Question,
    QuestionSituation,
)
from src.render.markdown import MarkdownRenderer
from src.render.terminal import TerminalRenderer
from tests.context.test_beat_scope import make_beat_config

CMMC = "Does CMMC Phase 2 slip past its statutory date?"
FEDRAMP = "Which CSPs move to FedRAMP authorized, and at which impact level?"
BOD = "Does any CISA BOD create a compliance obligation with a deadline inside 90 days?"


def make_beat(session, name="us-public-sector-compliance"):
    beat_id = ensure_beat(session, make_beat_config(name))
    session.flush()
    return beat_id


def add_beat_synthesis(session, beat_id, situations=None, generated_at=None):
    """A stored run attributed to a beat."""
    run = AnalysisRun(run_type="situation_synthesis", status="completed")
    session.add(run)
    session.flush()
    synthesis = NarrativeSynthesis(
        analysis_run_id=run.id,
        synthesis_data={"situations": situations or []},
        generated_at=generated_at or datetime(2026, 8, 20),
    )
    session.add(synthesis)
    session.flush()
    session.add(BeatRun(beat_id=beat_id, analysis_run_id=run.id, synthesis_id=synthesis.id))
    session.flush()
    return synthesis


def strip_ansi(text):
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestNoMovementPath:
    """A standing question with no coverage this run must still be reported."""

    def test_unmoved_question_still_appears(self, test_session):
        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (CMMC, FEDRAMP))
        test_session.commit()

        agenda = build_standing_agenda(test_session, beat_id, situations=[], movement={})

        assert len(agenda) == 2, "a quiet run must not drop standing questions"
        assert [entry["text"] for entry in agenda] == [CMMC, FEDRAMP]
        assert all(entry["moved"] is False for entry in agenda)
        assert all(entry["moved_in"] == [] for entry in agenda)
        assert all(entry["last_moved_at"] is None for entry in agenda)
        assert all(entry["appearance_count"] == 0 for entry in agenda)

    def test_unmoved_alongside_a_moved_one(self, test_session):
        """The quiet one survives a run where a sibling question did move."""
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC, FEDRAMP))
        test_session.commit()

        situations = [{"title": "DoD signals CMMC timeline pressure"}]
        agenda = build_standing_agenda(
            test_session, beat_id, situations, movement={seeded[0].id: [0]}
        )

        assert len(agenda) == 2
        assert agenda[0]["moved"] is True
        assert agenda[1]["moved"] is False
        assert agenda[1]["text"] == FEDRAMP

    def test_unmoved_question_reports_when_it_last_moved(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        previous = add_beat_synthesis(test_session, beat_id)
        test_session.add(
            QuestionSituation(
                question_id=seeded[0].id,
                synthesis_id=previous.id,
                situation_index=0,
                observed_at=datetime(2026, 8, 1, 12, 0),
            )
        )
        test_session.commit()

        entry = build_standing_agenda(test_session, beat_id, [], movement={})[0]

        assert entry["moved"] is False
        assert entry["last_moved_at"] == "2026-08-01"
        assert entry["appearance_count"] == 1, "prior movement still counts"

    def test_terminal_renders_the_unmoved_question(self, test_session):
        from src.render.document import BriefDocument

        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()
        agenda = build_standing_agenda(test_session, beat_id, [], movement={})

        doc = BriefDocument.from_synthesis_data(
            {"situations": [{"title": "Unrelated"}], "metadata": {"standing_agenda": agenda}}
        )
        out = strip_ansi(TerminalRenderer().render(doc))

        assert "STANDING AGENDA" in out
        assert CMMC in out
        assert "[NO MOVEMENT]" in out
        assert "No coverage this run bore on this question, and none ever has." in out

    def test_markdown_renders_the_unmoved_question(self, test_session):
        from src.render.document import BriefDocument

        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()
        agenda = build_standing_agenda(test_session, beat_id, [], movement={})

        doc = BriefDocument.from_synthesis_data({"metadata": {"standing_agenda": agenda}})
        out = MarkdownRenderer().render(doc)

        assert "## Standing agenda" in out
        assert f"### [NO MOVEMENT] {CMMC}" in out
        assert "No coverage this run bore on this question" in out

    def test_html_renders_the_unmoved_question(self, test_session):
        from src.render.document import BriefDocument
        from src.render.html import HTMLRenderer

        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()
        agenda = build_standing_agenda(test_session, beat_id, [], movement={})

        doc = BriefDocument.from_synthesis_data({"metadata": {"standing_agenda": agenda}})
        out = HTMLRenderer().render(doc)

        assert "<h2>Standing agenda</h2>" in out
        assert "[NO MOVEMENT]" in out

    def test_a_beat_with_no_declarations_renders_no_section(self, test_session):
        from src.render.document import BriefDocument

        beat_id = make_beat(test_session)
        test_session.commit()

        agenda = build_standing_agenda(test_session, beat_id, [], movement={})
        assert agenda == []

        doc = BriefDocument.from_synthesis_data(
            {"situations": [{"title": "x"}], "metadata": {"standing_agenda": agenda}}
        )
        assert "STANDING AGENDA" not in strip_ansi(TerminalRenderer().render(doc))


class TestSeeding:
    def test_seeds_questions_and_binds_them_to_the_beat(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC, FEDRAMP, BOD))
        test_session.commit()

        assert [q.text for q in seeded] == [CMMC, FEDRAMP, BOD]
        assert all(q.status == QUESTION_STATUS_OPEN for q in seeded)
        assert all(q.id is not None for q in seeded)

        links = test_session.query(BeatStandingQuestion).all()
        assert len(links) == 3
        assert {link.beat_id for link in links} == {beat_id}
        assert {link.question_id for link in links} == {q.id for q in seeded}
        assert {link.declared_text for link in links} == {CMMC, FEDRAMP, BOD}

    def test_seeding_is_idempotent_across_runs(self, test_session):
        beat_id = make_beat(test_session)
        first = seed_standing_questions(test_session, beat_id, (CMMC, FEDRAMP))
        test_session.commit()
        second = seed_standing_questions(test_session, beat_id, (CMMC, FEDRAMP))
        test_session.commit()

        assert [q.id for q in first] == [q.id for q in second]
        assert test_session.query(Question).count() == 2
        assert test_session.query(BeatStandingQuestion).count() == 2

    def test_reworded_declaration_seeds_a_new_question(self, test_session):
        """Normalization is the identity rule, so a real rewording is a new question."""
        beat_id = make_beat(test_session)
        first = seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()
        second = seed_standing_questions(
            test_session, beat_id, ("Does CMMC Phase 2 slip past its statutory deadline?",)
        )
        test_session.commit()

        assert first[0].id != second[0].id
        assert test_session.query(BeatStandingQuestion).count() == 2

    def test_punctuation_only_declaration_is_not_seeded(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, ("???",))
        test_session.commit()

        assert seeded == []
        assert test_session.query(Question).count() == 0

    def test_adopts_a_question_the_beat_already_raised(self, test_session):
        """Declaring a question the beat already asks keeps its accumulated history."""
        beat_id = make_beat(test_session)
        emergent = Question(
            text=CMMC,
            normalized_text="does cmmc phase 2 slip past its statutory date",
            status=QUESTION_STATUS_OPEN,
            first_asked_at=datetime(2026, 6, 1),
        )
        test_session.add(emergent)
        test_session.flush()
        synthesis = add_beat_synthesis(test_session, beat_id)
        test_session.add(
            QuestionSituation(question_id=emergent.id, synthesis_id=synthesis.id, situation_index=0)
        )
        test_session.commit()

        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()

        assert seeded[0].id == emergent.id
        assert test_session.query(Question).count() == 1
        assert build_standing_agenda(test_session, beat_id, [], {})[0]["appearance_count"] == 1

    def test_does_not_adopt_another_beats_question(self, test_session):
        other_beat = make_beat(test_session, "other-beat")
        mine = make_beat(test_session, "mine")
        theirs = Question(
            text=CMMC,
            normalized_text="does cmmc phase 2 slip past its statutory date",
            status=QUESTION_STATUS_OPEN,
        )
        test_session.add(theirs)
        test_session.flush()
        synthesis = add_beat_synthesis(test_session, other_beat)
        test_session.add(
            QuestionSituation(question_id=theirs.id, synthesis_id=synthesis.id, situation_index=0)
        )
        test_session.commit()

        seeded = seed_standing_questions(test_session, mine, (CMMC,))
        test_session.commit()

        assert seeded[0].id != theirs.id

    def test_empty_declaration_list_is_a_no_op(self, test_session):
        beat_id = make_beat(test_session)
        assert seed_standing_questions(test_session, beat_id, ()) == []
        assert test_session.query(Question).count() == 0

    def test_nothing_is_retired_when_a_declaration_is_removed(self, test_session):
        """Dropping a question from the config does not close it -- that is a judgement."""
        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (CMMC, FEDRAMP))
        test_session.commit()

        seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()

        assert test_session.query(Question).count() == 2
        assert all(q.status == QUESTION_STATUS_OPEN for q in test_session.query(Question).all())


class TestScoping:
    """A declared question belongs to its beat from the moment it is declared."""

    def test_seeded_question_is_not_in_the_default_scope(self, test_session):
        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()

        default = (
            test_session.query(Question).filter(question_scope_filter(test_session, None)).all()
        )
        assert default == [], "a declared question must not leak into the person brief's ledger"

    def test_seeded_question_is_in_its_beats_scope(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()

        in_beat = (
            test_session.query(Question).filter(question_scope_filter(test_session, beat_id)).all()
        )
        assert [q.id for q in in_beat] == [seeded[0].id]

    def test_seeded_question_is_not_in_another_beats_scope(self, test_session):
        mine = make_beat(test_session, "mine")
        theirs = make_beat(test_session, "theirs")
        seed_standing_questions(test_session, mine, (CMMC,))
        test_session.commit()

        assert (
            test_session.query(Question).filter(question_scope_filter(test_session, theirs)).all()
            == []
        )

    def test_declared_question_discloses_its_beat_before_it_ever_moves(self, test_session):
        beat_id = make_beat(test_session, "us-public-sector-compliance")
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()

        assert owning_beat_names(test_session, seeded[0].id) == ["us-public-sector-compliance"]

    def test_appearance_count_is_unaffected_by_declaration(self, test_session):
        """Declaring is not appearing: a seeded question starts at zero appearances."""
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()

        assert scoped_appearance_count(test_session, seeded[0].id, beat_id) == 0

    def test_default_scope_still_sees_unclaimed_questions(self, test_session):
        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (CMMC,))
        personal = Question(text="Will rates fall?", normalized_text="will rates fall")
        test_session.add(personal)
        test_session.commit()

        default = (
            test_session.query(Question).filter(question_scope_filter(test_session, None)).all()
        )
        assert [q.id for q in default] == [personal.id]


class TestMovement:
    def test_binding_coverage_to_a_standing_question(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC, FEDRAMP))
        test_session.commit()

        situations = [
            {"title": "FedRAMP authorizes two CSPs at High"},
            {"title": "DoD signals CMMC timeline pressure"},
        ]
        agenda = build_standing_agenda(
            test_session, beat_id, situations, movement={seeded[0].id: [1]}
        )

        cmmc = agenda[0]
        assert cmmc["moved"] is True
        assert cmmc["moved_in"] == [
            {"situation_index": 2, "title": "DoD signals CMMC timeline pressure"}
        ]
        assert cmmc["appearance_count"] == 1

    def test_movement_in_several_situations(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        test_session.commit()

        situations = [{"title": "First"}, {"title": "Second"}]
        entry = build_standing_agenda(
            test_session, beat_id, situations, movement={seeded[0].id: [0, 1]}
        )[0]

        assert [item["situation_index"] for item in entry["moved_in"]] == [1, 2]
        assert entry["appearance_count"] == 2

    def test_appearance_count_accumulates_across_runs(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        for day in (1, 8):
            synthesis = add_beat_synthesis(test_session, beat_id)
            test_session.add(
                QuestionSituation(
                    question_id=seeded[0].id,
                    synthesis_id=synthesis.id,
                    situation_index=0,
                    observed_at=datetime(2026, 8, day),
                )
            )
        test_session.commit()

        entry = build_standing_agenda(
            test_session, beat_id, [{"title": "Third"}], movement={seeded[0].id: [0]}
        )[0]

        assert entry["appearance_count"] == 3
        assert entry["last_moved_at"] == "2026-08-08"

    def test_another_beats_movement_does_not_count(self, test_session):
        """Appearance counts are per-scope, so a shared Question stays separated."""
        mine = make_beat(test_session, "mine")
        theirs = make_beat(test_session, "theirs")
        seeded = seed_standing_questions(test_session, mine, (CMMC,))
        other_synthesis = add_beat_synthesis(test_session, theirs)
        test_session.add(
            QuestionSituation(
                question_id=seeded[0].id, synthesis_id=other_synthesis.id, situation_index=0
            )
        )
        test_session.commit()

        entry = build_standing_agenda(test_session, mine, [], movement={})[0]
        assert entry["appearance_count"] == 0
        assert entry["last_moved_at"] is None

    def test_open_observables_are_surfaced(self, test_session):
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        synthesis = add_beat_synthesis(test_session, beat_id)
        test_session.add_all(
            [
                Prediction(
                    question_id=seeded[0].id,
                    observable_text="DFARS class deviation",
                    trigger_condition="published before the statutory date",
                    made_in_synthesis_id=synthesis.id,
                    status=PREDICTION_STATUS_OPEN,
                    made_at=datetime(2026, 8, 1),
                ),
                Prediction(
                    question_id=seeded[0].id,
                    observable_text="Already graded",
                    trigger_condition="irrelevant",
                    made_in_synthesis_id=synthesis.id,
                    status=PREDICTION_STATUS_TRIGGERED,
                    made_at=datetime(2026, 7, 1),
                ),
            ]
        )
        test_session.commit()

        entry = build_standing_agenda(test_session, beat_id, [], movement={})[0]
        assert entry["watching"] == ["DFARS class deviation -- published before the statutory date"]

    def test_resolved_standing_question_still_reports(self, test_session):
        """Resolving is a human act; the agenda reports the state, it does not hide it."""
        beat_id = make_beat(test_session)
        seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
        seeded[0].status = QUESTION_STATUS_RESOLVED
        seeded[0].resolved_at = datetime(2026, 8, 20)
        test_session.commit()

        entry = build_standing_agenda(test_session, beat_id, [], movement={})[0]
        assert entry["status"] == QUESTION_STATUS_RESOLVED
        assert entry["moved"] is False

    def test_declaration_order_is_preserved(self, test_session):
        beat_id = make_beat(test_session)
        seed_standing_questions(test_session, beat_id, (BOD, CMMC, FEDRAMP))
        test_session.commit()

        agenda = build_standing_agenda(test_session, beat_id, [], movement={})
        assert [entry["text"] for entry in agenda] == [BOD, CMMC, FEDRAMP]


class TestSynthesizerWiring:
    """The synthesizer's two seams into this module, without running a pipeline."""

    def test_question_movement_maps_situations_to_questions(self):
        from src.context.question_matcher import ProposedQuestion
        from src.context.synthesizer import NarrativeSynthesizer

        class FakeQuestion:
            def __init__(self, qid):
                self.id = qid

        plan = [
            (0, "primary", ProposedQuestion("a", True)),
            (0, "secondary:0", ProposedQuestion("b", False)),
            (2, "primary", ProposedQuestion("c", True)),
        ]
        resolved = [FakeQuestion(5), FakeQuestion(5), FakeQuestion(9)]

        movement = NarrativeSynthesizer._question_movement(plan, resolved)

        assert movement == {5: [0], 9: [2]}, "one question in one situation is one movement"

    def test_register_beat_seeds_the_declared_agenda(self, test_engine, monkeypatch):
        """_register_beat is the seam that makes seeding happen on the first run."""
        from contextlib import contextmanager

        from sqlalchemy.orm import sessionmaker

        from src.config.beats import BeatConfig, BeatSource
        from src.context import synthesizer as synth_module

        Session = sessionmaker(bind=test_engine)

        @contextmanager
        def fake_get_db():
            session = Session()
            try:
                yield session
            finally:
                session.close()

        monkeypatch.setattr(synth_module, "get_db", fake_get_db)

        beat = BeatConfig(
            name="us-public-sector-compliance",
            description="d",
            sources=(BeatSource(adapter="rss", feed_tags=("regulatory",)),),
            coverage={},
            standing_questions=(CMMC, FEDRAMP),
            channels=("terminal",),
            config_path="config/beats/us-public-sector-compliance.json",
        )

        beat_id = synth_module.NarrativeSynthesizer._register_beat(beat)

        check = Session()
        try:
            links = check.query(BeatStandingQuestion).all()
            assert len(links) == 2
            assert {link.beat_id for link in links} == {beat_id}
            assert {link.declared_text for link in links} == {CMMC, FEDRAMP}
        finally:
            check.close()

    def test_register_beat_is_idempotent(self, test_engine, monkeypatch):
        from contextlib import contextmanager

        from sqlalchemy.orm import sessionmaker

        from src.config.beats import BeatConfig, BeatSource
        from src.context import synthesizer as synth_module

        Session = sessionmaker(bind=test_engine)

        @contextmanager
        def fake_get_db():
            session = Session()
            try:
                yield session
            finally:
                session.close()

        monkeypatch.setattr(synth_module, "get_db", fake_get_db)

        beat = BeatConfig(
            name="b",
            description="d",
            sources=(BeatSource(adapter="rss", feed_tags=("regulatory",)),),
            coverage={},
            standing_questions=(CMMC,),
            channels=("terminal",),
            config_path="config/beats/b.json",
        )
        synth_module.NarrativeSynthesizer._register_beat(beat)
        synth_module.NarrativeSynthesizer._register_beat(beat)

        check = Session()
        try:
            assert check.query(BeatStandingQuestion).count() == 1
            assert check.query(Question).count() == 1
        finally:
            check.close()


class TestShippedBeat:
    """The compliance beat on disk must load and declare a usable agenda."""

    def test_shipped_beat_declares_standing_questions(self):
        from src.config.beats import load_beat

        beat = load_beat("us-public-sector-compliance")
        assert len(beat.standing_questions) >= 1
        assert all(isinstance(text, str) and text.strip() for text in beat.standing_questions)


@pytest.mark.parametrize(
    "declared_at,expected",
    [
        (datetime(2026, 8, 26, 14, 3), "2026-08-26"),
        (datetime(2026, 1, 1), "2026-01-01"),
    ],
)
def test_declared_at_is_a_date_string(test_session, declared_at, expected):
    beat_id = make_beat(test_session)
    seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
    link = (
        test_session.query(BeatStandingQuestion)
        .filter(BeatStandingQuestion.question_id == seeded[0].id)
        .one()
    )
    link.declared_at = declared_at
    test_session.commit()

    assert build_standing_agenda(test_session, beat_id, [], {})[0]["declared_at"] == expected


def test_agenda_survives_a_prior_run_gap(test_session):
    """A question that moved long ago and is quiet now reports both facts."""
    beat_id = make_beat(test_session)
    seeded = seed_standing_questions(test_session, beat_id, (CMMC,))
    synthesis = add_beat_synthesis(test_session, beat_id)
    test_session.add(
        QuestionSituation(
            question_id=seeded[0].id,
            synthesis_id=synthesis.id,
            situation_index=0,
            observed_at=datetime.now() - timedelta(days=60),
        )
    )
    test_session.commit()

    entry = build_standing_agenda(test_session, beat_id, [], movement={})[0]
    assert entry["moved"] is False
    assert entry["last_moved_at"] is not None
