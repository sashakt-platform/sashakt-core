import pytest

from app.core.quiz_json_import import (
    build_question_create,
    build_question_set_create,
    build_test_create,
    count_quiz_question_types,
)


def test_build_question_create_maps_choice_indexes_to_option_ids() -> None:
    question_create = build_question_create(
        {
            "text": "<p>What is 2 + 2?</p>",
            "type": "single-choice",
            "options": [
                {"text": "<p>3</p>"},
                {"text": "<p>4</p>"},
            ],
            "correct_answer": [1],
            "marking_scheme": {"correct": 4, "wrong": -1, "skipped": 0},
            "solution": ["<p>Because 2 + 2 = 4.</p>"],
        },
        organization_id=7,
    )

    assert question_create.question_type == "single-choice"
    assert question_create.options == [
        {"id": 1, "key": "A", "value": "<p>3</p>"},
        {"id": 2, "key": "B", "value": "<p>4</p>"},
    ]
    assert question_create.correct_answer == [2]
    assert question_create.solution == "<p>Because 2 + 2 = 4.</p>"


def test_build_test_create_preserves_section_metadata() -> None:
    chemistry_set = build_question_set_create(
        {
            "title": "Chemistry",
            "description": "Section 1",
            "max_questions_allowed_to_attempt": 25,
            "marking_scheme": {"correct": 4, "wrong": -1, "skipped": 0},
        },
        display_order=1,
        question_revision_ids=[11, 12],
    )
    maths_set = build_question_set_create(
        {
            "title": "Maths",
            "description": "Section 2",
            "max_questions_allowed_to_attempt": 25,
            "marking_scheme": {"correct": 4, "wrong": -1, "skipped": 0},
        },
        display_order=2,
        question_revision_ids=[21, 22, 23],
    )

    test_create = build_test_create(
        {
            "title": "Combined Chapter Test",
            "shuffle": True,
            "review_immediate": False,
            "display_solution": True,
            "time_limit": {"min": 0, "max": 7200},
            "metadata": {
                "source": "cms",
                "source_id": "68b67b243562d90ad5000fac",
                "quiz_type": "assessment",
            },
        },
        question_sets=[chemistry_set, maths_set],
        source_path="/tmp/quiz.json",
    )

    assert test_create.name == "Combined Chapter Test"
    assert test_create.time_limit == 120
    assert test_create.show_feedback_on_completion is True
    assert test_create.question_sets == [chemistry_set, maths_set]
    assert test_create.description is not None
    assert "source_id: 68b67b243562d90ad5000fac" in test_create.description
    assert "source_path: /tmp/quiz.json" in test_create.description


def test_build_question_set_create_allows_attempt_limit_override() -> None:
    question_set = build_question_set_create(
        {
            "title": "Maths",
            "description": "Section 2",
            "max_questions_allowed_to_attempt": 25,
        },
        display_order=2,
        question_revision_ids=[21, 22, 23, 24, 25],
        max_questions_allowed_to_attempt=3,
    )

    assert question_set.max_questions_allowed_to_attempt == 3


def test_count_quiz_question_types_normalizes_aliases() -> None:
    counts = count_quiz_question_types(
        {
            "question_sets": [
                {
                    "questions": [
                        {"type": "single-choice"},
                        {"type": "multi-choice"},
                        {"type": "numerical-float"},
                    ]
                }
            ]
        }
    )

    assert counts == {
        "single-choice": 1,
        "multi-choice": 1,
        "numerical-decimal": 1,
    }


def test_build_question_create_rejects_unsupported_types() -> None:
    with pytest.raises(ValueError, match="Unsupported quiz question type"):
        build_question_create(
            {
                "text": "Matrix question",
                "type": "matrix-match",
                "correct_answer": [],
            },
            organization_id=9,
        )
