from typing import Any

from sqlmodel import Session

from app.models import CandidateTest
from app.models.form import Form, FormResponse
from app.tests.utils.utils import random_lower_string


def create_form(
    session: Session,
    *,
    organization_id: int | None,
    created_by_id: int | None,
) -> Form:
    form = Form(
        name=random_lower_string(),
        organization_id=organization_id,
        created_by_id=created_by_id,
    )
    session.add(form)
    session.commit()
    session.refresh(form)
    return form


def create_form_response(
    session: Session,
    *,
    candidate_test: CandidateTest,
    form: Form,
    responses: dict[str, Any],
) -> FormResponse:
    form_response = FormResponse(
        candidate_test_id=candidate_test.id,
        form_id=form.id,
        responses=responses,
    )
    session.add(form_response)
    session.commit()
    session.refresh(form_response)
    return form_response
