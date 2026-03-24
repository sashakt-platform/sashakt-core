from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence

from app.models.question import QuestionRevision
from app.models.test import MarksLevelEnum, QuestionSet, Test, TestQuestion
from app.models.utils import MarkingScheme


def is_attempted_response(response: str | None) -> bool:
    return response is not None and response.strip() != ""


def normalize_question_set_ids(
    question_revision_ids: Sequence[int],
    question_set_ids: Sequence[int | None] | None,
) -> list[int | None]:
    normalized = list(question_set_ids or [])
    if len(normalized) < len(question_revision_ids):
        normalized.extend([None] * (len(question_revision_ids) - len(normalized)))
    return normalized[: len(question_revision_ids)]


def build_question_set_id_map(
    question_revision_ids: Sequence[int],
    question_set_ids: Sequence[int | None] | None,
) -> dict[int, int | None]:
    normalized = normalize_question_set_ids(question_revision_ids, question_set_ids)
    return {
        question_revision_id: normalized[index]
        for index, question_revision_id in enumerate(question_revision_ids)
    }


def group_question_ids_by_set(
    question_revision_ids: Sequence[int],
    question_set_ids: Sequence[int | None] | None,
) -> dict[int | None, list[int]]:
    normalized = normalize_question_set_ids(question_revision_ids, question_set_ids)
    grouped: dict[int | None, list[int]] = defaultdict(list)
    for index, question_revision_id in enumerate(question_revision_ids):
        grouped[normalized[index]].append(question_revision_id)
    return dict(grouped)


def is_sectioned_test(
    test_questions: Sequence[TestQuestion],
    question_sets_by_id: Mapping[int, QuestionSet] | None = None,
    *,
    test_id: int | None = None,
) -> bool:
    if not test_questions:
        return False

    has_null_membership = any(link.question_set_id is None for link in test_questions)
    has_section_membership = any(
        link.question_set_id is not None for link in test_questions
    )

    if has_null_membership and has_section_membership:
        raise ValueError("Mixed question-set membership is not allowed for a test.")

    if not has_section_membership:
        return False

    if question_sets_by_id is None:
        return True

    for test_question in test_questions:
        question_set_id = test_question.question_set_id
        if question_set_id is None:
            continue
        question_set = question_sets_by_id.get(question_set_id)
        if question_set is None:
            raise ValueError(
                f"Question set {question_set_id} referenced by test question was not found."
            )
        if test_id is not None and question_set.test_id != test_id:
            raise ValueError(
                f"Question set {question_set_id} does not belong to test {test_id}."
            )

    return True


def build_assigned_question_membership(
    test_questions: Sequence[TestQuestion],
    question_sets_by_id: Mapping[int, QuestionSet] | None = None,
    *,
    shuffle_questions: bool = False,
) -> tuple[list[int], list[int | None]]:
    ordered_links = sorted(test_questions, key=lambda link: (link.id or 0))
    sectioned = is_sectioned_test(ordered_links, question_sets_by_id)

    if not sectioned:
        flat_links = list(ordered_links)
        if shuffle_questions:
            random.shuffle(flat_links)
        return (
            [link.question_revision_id for link in flat_links],
            [None] * len(flat_links),
        )

    if question_sets_by_id is None:
        raise ValueError("Question-set metadata is required for sectioned tests.")

    grouped_links: dict[int, list[TestQuestion]] = defaultdict(list)
    for link in ordered_links:
        if link.question_set_id is None:
            raise ValueError(
                "Sectioned tests cannot contain null question_set_id values."
            )
        grouped_links[link.question_set_id].append(link)

    ordered_question_sets = sorted(
        question_sets_by_id.values(),
        key=lambda question_set: (question_set.display_order, question_set.id or 0),
    )

    assigned_question_revision_ids: list[int] = []
    assigned_question_set_ids: list[int | None] = []

    for question_set in ordered_question_sets:
        links = list(grouped_links.get(question_set.id or -1, []))
        if shuffle_questions:
            random.shuffle(links)
        for link in links:
            assigned_question_revision_ids.append(link.question_revision_id)
            assigned_question_set_ids.append(question_set.id)

    return assigned_question_revision_ids, assigned_question_set_ids


def get_effective_marking_scheme(
    test: Test,
    question_revision: QuestionRevision,
    *,
    question_set: QuestionSet | None = None,
    sectioned: bool = False,
) -> MarkingScheme | None:
    if sectioned:
        return (
            question_revision.marking_scheme
            or (question_set.marking_scheme if question_set else None)
            or test.marking_scheme
        )

    if test.marks_level == MarksLevelEnum.TEST:
        return test.marking_scheme

    return question_revision.marking_scheme or test.marking_scheme
