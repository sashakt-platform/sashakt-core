from types import SimpleNamespace
from typing import cast

import pytest

from app.core.question_sets import (
    build_assigned_question_membership,
    build_question_set_id_map,
    get_effective_marking_scheme,
    group_question_ids_by_set,
    is_attempted_response,
    is_sectioned_test,
    normalize_question_set_ids,
)
from app.models import question as question_models
from app.models import test as test_models


def make_link(
    link_id: int, question_revision_id: int, question_set_id: int | None
) -> test_models.TestQuestion:
    return test_models.TestQuestion(
        id=link_id,
        test_id=1,
        question_revision_id=question_revision_id,
        question_set_id=question_set_id,
    )


def make_question_set(
    question_set_id: int,
    *,
    display_order: int,
    test_id: int = 1,
    marking_scheme: dict[str, float] | None = None,
) -> test_models.QuestionSet:
    return test_models.QuestionSet(
        id=question_set_id,
        title=f"Section {question_set_id}",
        description=None,
        max_questions_allowed_to_attempt=2,
        display_order=display_order,
        marking_scheme=marking_scheme,
        test_id=test_id,
    )


def make_test_stub(
    *,
    marks_level: test_models.MarksLevelEnum,
    marking_scheme: dict[str, float] | None,
) -> test_models.Test:
    return cast(
        test_models.Test,
        SimpleNamespace(
            marks_level=marks_level,
            marking_scheme=marking_scheme,
        ),
    )


def make_question_revision_stub(
    *, marking_scheme: dict[str, float] | None
) -> question_models.QuestionRevision:
    return cast(
        question_models.QuestionRevision,
        SimpleNamespace(marking_scheme=marking_scheme),
    )


def make_question_set_stub(
    *, marking_scheme: dict[str, float] | None
) -> test_models.QuestionSet:
    return cast(
        test_models.QuestionSet,
        SimpleNamespace(marking_scheme=marking_scheme),
    )


class TestQuestionSetUtilities:
    def test_is_attempted_response(self) -> None:
        assert is_attempted_response("A") is True
        assert is_attempted_response("  A  ") is True
        assert is_attempted_response("") is False
        assert is_attempted_response("   ") is False
        assert is_attempted_response(None) is False

    def test_normalize_question_set_ids_pads_and_truncates(self) -> None:
        assert normalize_question_set_ids([1, 2, 3], [10]) == [10, None, None]
        assert normalize_question_set_ids([1, 2], [10, 20, 30]) == [10, 20]

    def test_build_question_set_id_map(self) -> None:
        assert build_question_set_id_map([11, 12, 13], [5, None]) == {
            11: 5,
            12: None,
            13: None,
        }

    def test_group_question_ids_by_set(self) -> None:
        assert group_question_ids_by_set([11, 12, 13, 14], [5, None, 5]) == {
            5: [11, 13],
            None: [12, 14],
        }


class TestSectionedTestDetection:
    def test_empty_and_flat_tests_are_not_sectioned(self) -> None:
        assert is_sectioned_test([]) is False
        assert (
            is_sectioned_test(
                [
                    make_link(1, 101, None),
                    make_link(2, 102, None),
                ]
            )
            is False
        )

    def test_mixed_membership_is_rejected(self) -> None:
        with pytest.raises(
            ValueError,
            match="Mixed question-set membership is not allowed for a test.",
        ):
            is_sectioned_test(
                [
                    make_link(1, 101, 10),
                    make_link(2, 102, None),
                ]
            )

    def test_missing_question_set_metadata_is_rejected(self) -> None:
        with pytest.raises(
            ValueError,
            match="Question set 10 referenced by test question was not found.",
        ):
            is_sectioned_test(
                [make_link(1, 101, 10)],
                question_sets_by_id={},
                test_id=1,
            )

    def test_question_set_from_other_test_is_rejected(self) -> None:
        with pytest.raises(
            ValueError,
            match="Question set 10 does not belong to test 1.",
        ):
            is_sectioned_test(
                [make_link(1, 101, 10)],
                question_sets_by_id={
                    10: make_question_set(10, display_order=1, test_id=2)
                },
                test_id=1,
            )

    def test_sectioned_test_with_valid_metadata_is_detected(self) -> None:
        assert is_sectioned_test(
            [make_link(1, 101, 10)],
            question_sets_by_id={10: make_question_set(10, display_order=1)},
            test_id=1,
        )


class TestAssignedQuestionMembership:
    def test_flat_test_keeps_order_and_uses_null_membership(self) -> None:
        question_revision_ids, question_set_ids = build_assigned_question_membership(
            [
                make_link(2, 102, None),
                make_link(1, 101, None),
            ]
        )

        assert question_revision_ids == [101, 102]
        assert question_set_ids == [None, None]

    def test_flat_test_shuffle_uses_shuffled_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def reverse_in_place(items: list[test_models.TestQuestion]) -> None:
            items.reverse()

        monkeypatch.setattr("app.core.question_sets.random.shuffle", reverse_in_place)

        question_revision_ids, question_set_ids = build_assigned_question_membership(
            [
                make_link(1, 101, None),
                make_link(2, 102, None),
            ],
            shuffle_questions=True,
        )

        assert question_revision_ids == [102, 101]
        assert question_set_ids == [None, None]

    def test_sectioned_test_requires_metadata(self) -> None:
        with pytest.raises(
            ValueError,
            match="Question-set metadata is required for sectioned tests.",
        ):
            build_assigned_question_membership([make_link(1, 101, 10)])

    def test_sectioned_test_orders_by_section_and_link_id(self) -> None:
        question_revision_ids, question_set_ids = build_assigned_question_membership(
            [
                make_link(3, 301, 20),
                make_link(2, 201, 10),
                make_link(1, 101, 20),
            ],
            question_sets_by_id={
                10: make_question_set(10, display_order=2),
                20: make_question_set(20, display_order=1),
            },
        )

        assert question_revision_ids == [101, 301, 201]
        assert question_set_ids == [20, 20, 10]

    def test_sectioned_test_shuffle_happens_within_each_section(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def reverse_in_place(items: list[test_models.TestQuestion]) -> None:
            items.reverse()

        monkeypatch.setattr("app.core.question_sets.random.shuffle", reverse_in_place)

        question_revision_ids, question_set_ids = build_assigned_question_membership(
            [
                make_link(1, 101, 10),
                make_link(2, 102, 10),
                make_link(3, 201, 20),
                make_link(4, 202, 20),
            ],
            question_sets_by_id={
                10: make_question_set(10, display_order=1),
                20: make_question_set(20, display_order=2),
            },
            shuffle_questions=True,
        )

        assert question_revision_ids == [102, 101, 202, 201]
        assert question_set_ids == [10, 10, 20, 20]


class TestEffectiveMarkingScheme:
    def test_sectioned_marking_prefers_question_revision(self) -> None:
        result = get_effective_marking_scheme(
            make_test_stub(
                marks_level=test_models.MarksLevelEnum.QUESTION,
                marking_scheme={"correct": 4.0, "wrong": -1.0, "skipped": 0.0},
            ),
            make_question_revision_stub(
                marking_scheme={"correct": 3.0, "wrong": -0.5, "skipped": 0.0}
            ),
            question_set=make_question_set_stub(
                marking_scheme={"correct": 2.0, "wrong": 0.0, "skipped": 0.0}
            ),
            sectioned=True,
        )

        assert result == {"correct": 3.0, "wrong": -0.5, "skipped": 0.0}

    def test_sectioned_marking_falls_back_to_question_set_then_test(self) -> None:
        test = make_test_stub(
            marks_level=test_models.MarksLevelEnum.QUESTION,
            marking_scheme={"correct": 4.0, "wrong": -1.0, "skipped": 0.0},
        )
        question_revision = make_question_revision_stub(marking_scheme=None)

        assert get_effective_marking_scheme(
            test,
            question_revision,
            question_set=make_question_set_stub(
                marking_scheme={"correct": 2.0, "wrong": 0.0, "skipped": 0.0}
            ),
            sectioned=True,
        ) == {"correct": 2.0, "wrong": 0.0, "skipped": 0.0}
        assert get_effective_marking_scheme(
            test,
            question_revision,
            question_set=None,
            sectioned=True,
        ) == {"correct": 4.0, "wrong": -1.0, "skipped": 0.0}

    def test_non_sectioned_test_level_marking_uses_test_scheme(self) -> None:
        result = get_effective_marking_scheme(
            make_test_stub(
                marks_level=test_models.MarksLevelEnum.TEST,
                marking_scheme={"correct": 4.0, "wrong": -1.0, "skipped": 0.0},
            ),
            make_question_revision_stub(
                marking_scheme={"correct": 2.0, "wrong": 0.0, "skipped": 0.0}
            ),
            sectioned=False,
        )

        assert result == {"correct": 4.0, "wrong": -1.0, "skipped": 0.0}

    def test_non_sectioned_question_level_marking_prefers_question_scheme(self) -> None:
        test = make_test_stub(
            marks_level=test_models.MarksLevelEnum.QUESTION,
            marking_scheme={"correct": 4.0, "wrong": -1.0, "skipped": 0.0},
        )

        assert get_effective_marking_scheme(
            test,
            make_question_revision_stub(
                marking_scheme={"correct": 2.0, "wrong": 0.0, "skipped": 0.0}
            ),
            sectioned=False,
        ) == {"correct": 2.0, "wrong": 0.0, "skipped": 0.0}
        assert get_effective_marking_scheme(
            test,
            make_question_revision_stub(marking_scheme=None),
            sectioned=False,
        ) == {"correct": 4.0, "wrong": -1.0, "skipped": 0.0}


class TestQuestionSetValidators:
    def test_test_create_rejects_mixed_question_membership_inputs(self) -> None:
        with pytest.raises(
            ValueError,
            match="Use either question_revision_ids or question_sets, not both.",
        ):
            test_models.TestCreate(
                name="Sectioned test",
                question_revision_ids=[101],
                question_sets=[
                    test_models.QuestionSetCreate(
                        title="Section 1",
                        max_questions_allowed_to_attempt=1,
                        display_order=1,
                        question_revision_ids=[101],
                    )
                ],
            )

    def test_test_update_rejects_mixed_question_membership_inputs(self) -> None:
        with pytest.raises(
            ValueError,
            match="Use either question_revision_ids or question_sets, not both.",
        ):
            test_models.TestUpdate(
                name="Sectioned test",
                locale="en-US",
                question_revision_ids=[101],
                question_sets=[
                    test_models.QuestionSetUpdate(
                        id=10,
                        title="Section 1",
                        max_questions_allowed_to_attempt=1,
                        display_order=1,
                        question_revision_ids=[101],
                    )
                ],
            )
