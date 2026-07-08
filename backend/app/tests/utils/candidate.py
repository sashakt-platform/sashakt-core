from sqlmodel import Session

from app.models import Candidate, CandidateTest, Test
from app.tests.utils.utils import random_lower_string


def create_test_candidate(
    session: Session,
    *,
    organization_id: int | None = None,
    user_id: int | None = None,
) -> Candidate:
    candidate = Candidate(organization_id=organization_id, user_id=user_id)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


def create_test_record(
    session: Session,
    *,
    user_id: int | None,
    organization_id: int | None,
    marks_level: str | None = None,
    form_id: int | None = None,
) -> Test:
    test = Test(
        name=random_lower_string(),
        created_by_id=user_id,
        organization_id=organization_id,
        is_active=True,
        link=random_lower_string(),
        marks_level=marks_level,
        form_id=form_id,
    )
    session.add(test)
    session.commit()
    session.refresh(test)
    return test


def create_test_candidate_test(
    session: Session,
    *,
    admin_id: int | None,
    test_id: int | None,
    candidate_id: int | None,
    question_revision_ids: list[int | None] | None = None,
    is_submitted: bool = False,
    start_time: str = "2026-06-10T10:00:00",
    end_time: str | None = None,
) -> CandidateTest:
    candidate_test = CandidateTest(
        admin_id=admin_id,
        test_id=test_id,
        candidate_id=candidate_id,
        device=random_lower_string(),
        consent=True,
        start_time=start_time,
        end_time=end_time,
        is_submitted=is_submitted,
        question_revision_ids=question_revision_ids or [],
        question_set_ids=[None] if question_revision_ids else [],
    )
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)
    return candidate_test
