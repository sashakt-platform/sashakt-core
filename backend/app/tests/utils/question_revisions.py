from sqlmodel import Session

from app.models import Question, QuestionRevision
from app.tests.utils.organization import create_random_organization
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string


def create_random_question_revision(session: Session) -> QuestionRevision:
    user = create_random_user(session)
    organization = create_random_organization(session)

    question = Question(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        organization_id=organization.id,
        question_type="single-choice",
        is_mandatory=True,
    )

    session.add(question)
    session.commit()
    session.refresh(question)

    question_revision = QuestionRevision(
        question_text=random_lower_string(),
        question_type="single-choice",
        question_id=question.id,
        revision_number=1,
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        organization_id=organization.id,
    )
    session.add(question_revision)
    session.commit()
    session.refresh(question_revision)
    return question_revision
