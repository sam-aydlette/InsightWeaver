"""
Tests for beat scoping of the commitment graph.

The graph tables carry no ``beat_id`` column; a row's beat is derived from the
``beat_runs`` join. These tests pin the two properties that decision rests on:

1. A beat and the default brief cannot see each other's questions, predictions
   or appearance counts.
2. With no beat runs on record -- every database that predates this feature --
   the default scope is the whole graph, so nothing about the existing brief
   changes.

Everything here runs against the per-test SQLite file from ``test_engine``.
Nothing touches the configured DATABASE_URL.
"""

from datetime import datetime

import pytest

from src.config.beats import BeatConfig, BeatSource
from src.context.beat_scope import (
    ensure_beat,
    prediction_scope_filter,
    question_scope_filter,
    scoped_appearance_count,
)
from src.database.models import (
    PREDICTION_STATUS_OPEN,
    QUESTION_STATUS_OPEN,
    AnalysisRun,
    Beat,
    BeatRun,
    NarrativeSynthesis,
    Prediction,
    Question,
    QuestionSituation,
)


def make_beat_config(name="test-beat"):
    return BeatConfig(
        name=name,
        description=f"{name} description",
        sources=(BeatSource(adapter="rss", feed_tags=("regulatory",)),),
        watchlist={},
        standing_questions=(),
        channels=("terminal",),
        config_path=f"config/beats/{name}.json",
    )


def add_synthesis(session):
    """A stored run, with no beat attribution unless one is added."""
    run = AnalysisRun(run_type="situation_synthesis", status="completed")
    session.add(run)
    session.flush()
    synthesis = NarrativeSynthesis(analysis_run_id=run.id)
    session.add(synthesis)
    session.flush()
    return run, synthesis


def attribute(session, synthesis, run, beat_id):
    session.add(BeatRun(beat_id=beat_id, analysis_run_id=run.id, synthesis_id=synthesis.id))
    session.flush()


def add_question(session, text, synthesis, situation_index=0):
    """A question that appeared in one synthesis."""
    question = Question(
        text=text,
        normalized_text=text.lower(),
        status=QUESTION_STATUS_OPEN,
        first_asked_at=datetime(2026, 3, 12, 10, 0, 0),
    )
    session.add(question)
    session.flush()
    session.add(
        QuestionSituation(
            question_id=question.id,
            synthesis_id=synthesis.id,
            situation_index=situation_index,
        )
    )
    session.flush()
    return question


def questions_in_scope(session, beat_id):
    return {
        q.text
        for q in session.query(Question).filter(question_scope_filter(session, beat_id)).all()
    }


class TestEnsureBeat:
    def test_creates_the_row_once(self, test_session):
        config = make_beat_config()

        first = ensure_beat(test_session, config)
        second = ensure_beat(test_session, config)

        assert first == second
        assert test_session.query(Beat).count() == 1

    def test_refreshes_description_from_config(self, test_session):
        ensure_beat(test_session, make_beat_config())
        beat_id = ensure_beat(
            test_session,
            BeatConfig(
                name="test-beat",
                description="rewritten",
                sources=(BeatSource(adapter="rss", feed_tags=("x",)),),
                watchlist={},
                standing_questions=(),
                channels=("terminal",),
                config_path="config/beats/test-beat.json",
            ),
        )

        row = test_session.query(Beat).filter(Beat.id == beat_id).one()
        assert row.description == "rewritten"

    def test_distinct_beats_get_distinct_ids(self, test_session):
        first = ensure_beat(test_session, make_beat_config("beat-a"))
        second = ensure_beat(test_session, make_beat_config("beat-b"))

        assert first != second


class TestDefaultScopeWithoutBeats:
    """
    The state of every existing database: no beat_runs rows at all. The default
    scope must be the entire graph, i.e. the pre-beat behaviour.
    """

    def test_every_question_is_in_the_default_scope(self, test_session):
        _, synthesis = add_synthesis(test_session)
        add_question(test_session, "Will A?", synthesis)
        add_question(test_session, "Will B?", synthesis)

        assert questions_in_scope(test_session, None) == {"Will A?", "Will B?"}

    def test_appearance_count_is_the_total_count(self, test_session):
        _, first = add_synthesis(test_session)
        _, second = add_synthesis(test_session)
        question = add_question(test_session, "Will A?", first)
        test_session.add(
            QuestionSituation(question_id=question.id, synthesis_id=second.id, situation_index=0)
        )
        test_session.flush()

        assert scoped_appearance_count(test_session, question.id, None) == 2

    def test_every_open_prediction_is_in_the_default_scope(self, test_session):
        _, synthesis = add_synthesis(test_session)
        question = add_question(test_session, "Will A?", synthesis)
        test_session.add(
            Prediction(
                question_id=question.id,
                observable_text="Rule published",
                trigger_condition="It appears in the Federal Register",
                made_in_synthesis_id=synthesis.id,
                status=PREDICTION_STATUS_OPEN,
            )
        )
        test_session.flush()

        found = (
            test_session.query(Prediction).filter(prediction_scope_filter(test_session, None)).all()
        )
        assert len(found) == 1


class TestScopesDoNotCollide:
    @pytest.fixture
    def two_scopes(self, test_session):
        """One beat run and one default run, each with their own question."""
        beat_id = ensure_beat(test_session, make_beat_config("compliance"))

        beat_run, beat_synthesis = add_synthesis(test_session)
        attribute(test_session, beat_synthesis, beat_run, beat_id)
        beat_question = add_question(test_session, "Will the CUI rule take effect?", beat_synthesis)

        _, default_synthesis = add_synthesis(test_session)
        default_question = add_question(
            test_session, "Will the school board reverse itself?", default_synthesis
        )

        return {
            "beat_id": beat_id,
            "beat_synthesis": beat_synthesis,
            "beat_question": beat_question,
            "default_synthesis": default_synthesis,
            "default_question": default_question,
        }

    def test_beat_scope_sees_only_its_own_questions(self, test_session, two_scopes):
        assert questions_in_scope(test_session, two_scopes["beat_id"]) == {
            "Will the CUI rule take effect?"
        }

    def test_default_scope_excludes_beat_questions(self, test_session, two_scopes):
        assert questions_in_scope(test_session, None) == {"Will the school board reverse itself?"}

    def test_two_beats_do_not_see_each_other(self, test_session, two_scopes):
        other_id = ensure_beat(test_session, make_beat_config("other"))
        other_run, other_synthesis = add_synthesis(test_session)
        attribute(test_session, other_synthesis, other_run, other_id)
        add_question(test_session, "Will something else happen?", other_synthesis)

        assert questions_in_scope(test_session, other_id) == {"Will something else happen?"}
        assert questions_in_scope(test_session, two_scopes["beat_id"]) == {
            "Will the CUI rule take effect?"
        }

    def test_appearance_count_is_per_scope(self, test_session, two_scopes):
        """
        The load-bearing case. A question that appears in both a beat run and a
        default run must report each scope's own run number, not the sum --
        the brief prints that number as the question's identity.
        """
        question = two_scopes["beat_question"]
        default_synthesis = two_scopes["default_synthesis"]
        test_session.add(
            QuestionSituation(
                question_id=question.id,
                synthesis_id=default_synthesis.id,
                situation_index=1,
            )
        )
        test_session.flush()

        assert scoped_appearance_count(test_session, question.id, two_scopes["beat_id"]) == 1
        assert scoped_appearance_count(test_session, question.id, None) == 1

    def test_predictions_follow_their_question_scope(self, test_session, two_scopes):
        for key, synthesis_key in (
            ("beat_question", "beat_synthesis"),
            ("default_question", "default_synthesis"),
        ):
            test_session.add(
                Prediction(
                    question_id=two_scopes[key].id,
                    observable_text=f"observable for {key}",
                    trigger_condition="something happens",
                    made_in_synthesis_id=two_scopes[synthesis_key].id,
                    status=PREDICTION_STATUS_OPEN,
                )
            )
        test_session.flush()

        beat_preds = (
            test_session.query(Prediction)
            .filter(prediction_scope_filter(test_session, two_scopes["beat_id"]))
            .all()
        )
        default_preds = (
            test_session.query(Prediction).filter(prediction_scope_filter(test_session, None)).all()
        )

        assert [p.observable_text for p in beat_preds] == ["observable for beat_question"]
        assert [p.observable_text for p in default_preds] == ["observable for default_question"]

    def test_unattributed_run_stays_in_the_default_scope(self, test_session, two_scopes):
        """A beat_runs row with no synthesis_id claims nothing."""
        run, synthesis = add_synthesis(test_session)
        test_session.add(
            BeatRun(beat_id=two_scopes["beat_id"], analysis_run_id=run.id, synthesis_id=None)
        )
        test_session.flush()
        add_question(test_session, "Orphan question?", synthesis)

        assert "Orphan question?" in questions_in_scope(test_session, None)
        assert "Orphan question?" not in questions_in_scope(test_session, two_scopes["beat_id"])


class TestBeatRunRecordsTheRun:
    def test_a_beat_accumulates_runs(self, test_session):
        beat_id = ensure_beat(test_session, make_beat_config("compliance"))
        for _ in range(3):
            run, synthesis = add_synthesis(test_session)
            attribute(test_session, synthesis, run, beat_id)

        beat = test_session.query(Beat).filter(Beat.id == beat_id).one()
        assert len(beat.runs) == 3
        assert all(r.beat_id == beat_id for r in beat.runs)


class TestUnmigratedDatabase:
    """
    A database that predates beats has no ``beat_runs`` table at all. The
    default brief must keep working on it untouched -- that is what makes
    "brief with no --beat behaves exactly as today" true of every existing
    database, not only of ones that have run the migration.
    """

    @pytest.fixture
    def pre_beat_session(self, tmp_path):
        """A session on a schema built without the two beat tables."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from src.database.models import Base

        engine = create_engine(f"sqlite:///{tmp_path / 'pre-beat.db'}")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                table
                for name, table in Base.metadata.tables.items()
                if name not in ("beats", "beat_runs")
            ],
        )
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    def test_the_beat_tables_really_are_absent(self, pre_beat_session):
        from sqlalchemy import inspect

        names = inspect(pre_beat_session.get_bind()).get_table_names()
        assert "beat_runs" not in names
        assert "questions" in names

    def test_default_question_scope_still_works(self, pre_beat_session):
        _, synthesis = add_synthesis(pre_beat_session)
        add_question(pre_beat_session, "Will A?", synthesis)

        assert questions_in_scope(pre_beat_session, None) == {"Will A?"}

    def test_default_prediction_scope_still_works(self, pre_beat_session):
        _, synthesis = add_synthesis(pre_beat_session)
        question = add_question(pre_beat_session, "Will A?", synthesis)
        pre_beat_session.add(
            Prediction(
                question_id=question.id,
                observable_text="Rule published",
                trigger_condition="It appears",
                made_in_synthesis_id=synthesis.id,
                status=PREDICTION_STATUS_OPEN,
            )
        )
        pre_beat_session.flush()

        found = (
            pre_beat_session.query(Prediction)
            .filter(prediction_scope_filter(pre_beat_session, None))
            .all()
        )
        assert len(found) == 1

    def test_default_appearance_count_still_works(self, pre_beat_session):
        _, synthesis = add_synthesis(pre_beat_session)
        question = add_question(pre_beat_session, "Will A?", synthesis)

        assert scoped_appearance_count(pre_beat_session, question.id, None) == 1

    def test_a_beat_run_on_an_unmigrated_database_fails_loudly(self, pre_beat_session):
        """
        The other half of the contract: a beat run must not silently degrade
        into an unscoped run. Registering the beat is the first thing it does,
        and that is where an unmigrated database stops it.
        """
        from sqlalchemy.exc import OperationalError

        with pytest.raises(OperationalError):
            ensure_beat(pre_beat_session, make_beat_config())
