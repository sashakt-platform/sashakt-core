from __future__ import annotations

import math
from collections import Counter
from typing import Any

from app.models.question import QuestionCreate, QuestionType
from app.models.test import QuestionSetCreate, TestCreate

QUESTION_TYPE_ALIASES: dict[str, QuestionType] = {
    QuestionType.single_choice.value: QuestionType.single_choice,
    QuestionType.multi_choice.value: QuestionType.multi_choice,
    "multiple-choice": QuestionType.multi_choice,
    QuestionType.subjective.value: QuestionType.subjective,
    QuestionType.numerical_integer.value: QuestionType.numerical_integer,
    "numerical-float": QuestionType.numerical_decimal,
    QuestionType.numerical_decimal.value: QuestionType.numerical_decimal,
}

OPTION_KEYS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def normalize_question_type(raw_type: Any) -> QuestionType:
    if not isinstance(raw_type, str):
        raise ValueError(
            f"Question type must be a string, got {type(raw_type).__name__}."
        )

    question_type = QUESTION_TYPE_ALIASES.get(raw_type)
    if question_type is None:
        supported_types = ", ".join(sorted(QUESTION_TYPE_ALIASES))
        raise ValueError(
            f"Unsupported quiz question type '{raw_type}'. Supported types: {supported_types}."
        )
    return question_type


def build_import_description(
    metadata: dict[str, Any] | None, *, source_path: str | None = None
) -> str:
    metadata = metadata or {}
    description_parts = ["Imported from quiz JSON."]
    if source_path:
        description_parts.append(f"source_path: {source_path}")
    for key in ("source", "source_id", "quiz_type", "subject", "grade", "test_format"):
        value = metadata.get(key)
        if value not in (None, ""):
            description_parts.append(f"{key}: {value}")
    return "\n".join(description_parts)


def convert_time_limit_to_minutes(raw_time_limit: Any) -> int | None:
    if raw_time_limit is None:
        return None

    if isinstance(raw_time_limit, dict):
        seconds = raw_time_limit.get("max")
    else:
        seconds = raw_time_limit

    if seconds in (None, 0):
        return None

    if not isinstance(seconds, int | float):
        raise ValueError(f"Unsupported time_limit value: {seconds!r}")

    return max(1, math.ceil(float(seconds) / 60))


def transform_choice_options(
    raw_options: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    options = raw_options or []
    if not options:
        raise ValueError("Choice questions must include at least one option.")

    transformed_options: list[dict[str, Any]] = []
    for index, option in enumerate(options, start=1):
        key = OPTION_KEYS[index - 1] if index <= len(OPTION_KEYS) else str(index)
        transformed_options.append(
            {
                "id": index,
                "key": key,
                "value": str(option.get("text") or ""),
            }
        )
    return transformed_options


def normalize_correct_answer(
    *,
    question_type: QuestionType,
    raw_correct_answer: Any,
    option_count: int,
) -> Any:
    if question_type in (QuestionType.single_choice, QuestionType.multi_choice):
        if not isinstance(raw_correct_answer, list):
            raise ValueError("Choice questions must use a list of option indexes.")

        normalized_answers: list[int] = []
        for answer in raw_correct_answer:
            if not isinstance(answer, int):
                raise ValueError(
                    f"Choice question answers must be integers, got {answer!r}."
                )
            if answer < 0 or answer >= option_count:
                raise ValueError(
                    f"Choice answer index {answer} is out of range for"
                    f" {option_count} options."
                )
            normalized_answers.append(answer + 1)
        return normalized_answers

    if question_type == QuestionType.subjective:
        return raw_correct_answer

    if raw_correct_answer is None:
        return None

    if isinstance(raw_correct_answer, list):
        if len(raw_correct_answer) != 1:
            raise ValueError(
                f"{question_type.value} questions must have a single scalar answer."
            )
        raw_correct_answer = raw_correct_answer[0]

    if question_type == QuestionType.numerical_integer:
        if isinstance(raw_correct_answer, bool):
            raise ValueError("Boolean values are not valid integer answers.")
        return int(raw_correct_answer)

    if question_type == QuestionType.numerical_decimal:
        if isinstance(raw_correct_answer, bool):
            raise ValueError("Boolean values are not valid decimal answers.")
        return float(raw_correct_answer)

    return raw_correct_answer


def build_question_create(
    question_payload: dict[str, Any],
    *,
    organization_id: int,
    state_ids: list[int] | None = None,
    district_ids: list[int] | None = None,
) -> QuestionCreate:
    question_type = normalize_question_type(question_payload.get("type"))
    options = (
        transform_choice_options(question_payload.get("options"))
        if question_type in (QuestionType.single_choice, QuestionType.multi_choice)
        else None
    )
    correct_answer = normalize_correct_answer(
        question_type=question_type,
        raw_correct_answer=question_payload.get("correct_answer"),
        option_count=len(options or []),
    )
    solution = question_payload.get("solution")
    if isinstance(solution, list):
        solution = "\n\n".join(str(part) for part in solution if part not in (None, ""))
    elif solution is not None:
        solution = str(solution)

    return QuestionCreate(
        organization_id=organization_id,
        question_text=str(question_payload.get("text") or ""),
        instructions=None,
        question_type=question_type,
        options=options,
        correct_answer=correct_answer,
        subjective_answer_limit=question_payload.get("max_char_limit"),
        is_mandatory=True,
        is_active=True,
        marking_scheme=question_payload.get("marking_scheme"),
        solution=solution,
        media=None,
        state_ids=state_ids or [],
        district_ids=district_ids or [],
        block_ids=[],
        tag_ids=[],
    )


def build_question_set_create(
    question_set_payload: dict[str, Any],
    *,
    display_order: int,
    question_revision_ids: list[int],
    max_questions_allowed_to_attempt: int | None = None,
) -> QuestionSetCreate:
    resolved_attempt_limit = max_questions_allowed_to_attempt
    if resolved_attempt_limit is None:
        resolved_attempt_limit = question_set_payload.get(
            "max_questions_allowed_to_attempt"
        ) or len(question_revision_ids)

    return QuestionSetCreate(
        title=str(question_set_payload.get("title") or f"Section {display_order}"),
        description=question_set_payload.get("description"),
        max_questions_allowed_to_attempt=resolved_attempt_limit,
        display_order=display_order,
        marking_scheme=question_set_payload.get("marking_scheme"),
        question_revision_ids=question_revision_ids,
    )


def count_quiz_question_types(quiz_payload: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for question_set in quiz_payload.get("question_sets") or []:
        for question in question_set.get("questions") or []:
            normalized_type = normalize_question_type(question.get("type"))
            counts[normalized_type.value] += 1
    return counts


def build_test_create(
    quiz_payload: dict[str, Any],
    *,
    question_sets: list[QuestionSetCreate],
    source_path: str | None = None,
    state_ids: list[int] | None = None,
    district_ids: list[int] | None = None,
) -> TestCreate:
    return TestCreate(
        name=str(quiz_payload.get("title") or "Imported Quiz"),
        description=build_import_description(
            quiz_payload.get("metadata"),
            source_path=source_path,
        ),
        time_limit=convert_time_limit_to_minutes(quiz_payload.get("time_limit")),
        marks_level="question",
        shuffle=bool(quiz_payload.get("shuffle", False)),
        no_of_attempts=1,
        show_result=True,
        show_feedback_immediately=bool(quiz_payload.get("review_immediate", False)),
        show_feedback_on_completion=bool(quiz_payload.get("display_solution", False)),
        question_sets=question_sets,
        question_revision_ids=[],
        tag_ids=[],
        state_ids=state_ids or [],
        district_ids=district_ids or [],
        random_tag_count=None,
    )
