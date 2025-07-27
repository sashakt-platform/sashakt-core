from sqlmodel import Session

from app.models import Question, QuestionRevision
from app.models.organization import Organization
from app.models.user import User
from app.tests.utils.organization import create_random_organization
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string


def create_random_question_revision(
    session: Session, user_id: int | None = None, org_id: int | None = None
) -> QuestionRevision:
    if user_id is None:
        user = create_random_user(session)
        user_id = user.id
    else:
        user_obj = session.get(User, user_id)
        if user_obj is None:
            raise Exception("User Not Found")
        user = user_obj
    if org_id is None:
        organization = create_random_organization(session)
        org_id = organization.id
    else:
        org_obj = session.get(Organization, org_id)
        if org_obj is None:
            raise Exception("Organization Not Found")
        organization = org_obj
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
