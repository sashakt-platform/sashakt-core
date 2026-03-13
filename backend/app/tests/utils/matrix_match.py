from typing import Any

from sqlmodel import Session

from app.models import Question, QuestionRevision, Test, TestQuestion
from app.models.organization import Organization
from app.models.question import QuestionType
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string

MATRIX_MATCH_OPTIONS = {
    "rows": {
        "label": "Column A",
        "items": [
            {"id": 1, "key": "P", "value": "Item P"},
            {"id": 2, "key": "Q", "value": "Item Q"},
            {"id": 3, "key": "R", "value": "Item R"},
        ],
    },
    "columns": {
        "label": "Column B",
        "items": [
            {"id": 10, "key": "1", "value": "Item 1"},
            {"id": 20, "key": "2", "value": "Item 2"},
            {"id": 30, "key": "3", "value": "Item 3"},
        ],
    },
}

MATRIX_MATCH_CORRECT_ANSWER = {"1": [10, 20], "2": [20], "3": [30]}


def create_matrix_match_test_setup(
    session: Session,
    marking_scheme: dict[str, Any] | None = None,
    correct_answer: dict[str, list[int]] | None = None,
) -> tuple[Test, QuestionRevision]:
    if marking_scheme is None:
        marking_scheme = {"correct": 4, "wrong": -1, "skipped": 0}

    if correct_answer is None:
        correct_answer = MATRIX_MATCH_CORRECT_ANSWER

    user = create_random_user(session)

    org = Organization(name=random_lower_string())
    session.add(org)
    session.commit()
    session.refresh(org)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        marks_level="question",
    )
    session.add(test)
    session.commit()
    session.refresh(test)

    question = Question(organization_id=org.id)
    session.add(question)
    session.commit()
    session.refresh(question)

    revision = QuestionRevision(
        created_by_id=user.id,
        question_id=question.id,
        question_text=random_lower_string(),
        question_type=QuestionType.matrix_match,
        options=MATRIX_MATCH_OPTIONS,
        correct_answer=correct_answer,
        is_mandatory=True,
        is_active=True,
        marking_scheme=marking_scheme,
    )
    session.add(revision)
    session.commit()
    session.refresh(revision)

    session.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    session.commit()

    return test, revision
