from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.orm import selectinload
from sqlmodel import func, select

from app.api.deps import CurrentUser, Pagination, SessionDep, permission_dependency
from app.models import Message
from app.models.form import (
    Form,
    FormCreate,
    FormField,
    FormFieldCreate,
    FormFieldPublic,
    FormFieldReorder,
    FormFieldUpdate,
    FormPublic,
    FormResponse,
    FormResponsePublic,
    FormUpdate,
)

router = APIRouter(
    prefix="/form",
    tags=["Form"],
)


def transform_forms_to_public(
    forms: list[Form] | Any,
) -> list[FormPublic]:
    """Transform Form models to FormPublic with nested fields."""
    result: list[FormPublic] = []
    form_list: list[Form] = list(forms) if not isinstance(forms, list) else forms

    for form in form_list:
        fields_public = [
            FormFieldPublic(**field.model_dump()) for field in (form.fields or [])
        ]
        result.append(
            FormPublic(
                **form.model_dump(exclude={"fields"}),
                fields=fields_public,
            )
        )
    return result


def build_form_public(form: Form) -> FormPublic:
    """Build a FormPublic response from a Form model."""
    fields_public = [
        FormFieldPublic(**field.model_dump()) for field in (form.fields or [])
    ]
    return FormPublic(
        **form.model_dump(exclude={"fields"}),
        fields=fields_public,
    )


# ============== Form CRUD Endpoints ==============


@router.post(
    "/",
    response_model=FormPublic,
    dependencies=[Depends(permission_dependency("create_form"))],
)
def create_form(
    form_create: FormCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> FormPublic:
    """Create a new form."""
    # Use current user's organization if not specified
    organization_id = form_create.organization_id or current_user.organization_id

    # Check for duplicate form name within organization
    normalized_name = form_create.name.strip().lower()
    existing = session.exec(
        select(Form)
        .where(func.lower(func.trim(Form.name)) == normalized_name)
        .where(Form.organization_id == organization_id)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Form with name '{form_create.name}' already exists in this organization.",
        )

    form = Form(
        name=form_create.name,
        description=form_create.description,
        is_active=form_create.is_active,
        organization_id=organization_id,
        created_by_id=current_user.id,
    )

    session.add(form)
    session.commit()
    session.refresh(form)

    return build_form_public(form)


@router.get(
    "/",
    response_model=Page[FormPublic],
    dependencies=[Depends(permission_dependency("read_form"))],
)
def get_forms(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    name: str | None = None,
    is_active: bool | None = None,
) -> Page[FormPublic]:
    """Get all forms for the current user's organization."""
    query = (
        select(Form)
        .options(selectinload(Form.fields))  # type: ignore[arg-type]
        .where(Form.organization_id == current_user.organization_id)
    )

    if name:
        query = query.where(
            func.lower(Form.name).contains(name.strip().lower(), autoescape=True)
        )

    if is_active is not None:
        query = query.where(Form.is_active == is_active)

    # Order by created_date descending (newest first)
    query = query.order_by(Form.created_date.desc())  # type: ignore[union-attr]

    forms: Page[FormPublic] = paginate(
        session,
        query,  # type: ignore[arg-type]
        params,
        transformer=lambda items: transform_forms_to_public(items),
    )

    return forms


@router.get(
    "/{form_id}",
    response_model=FormPublic,
    dependencies=[Depends(permission_dependency("read_form"))],
)
def get_form_by_id(
    form_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> FormPublic:
    """Get a form by ID."""
    form = session.exec(
        select(Form)
        .options(selectinload(Form.fields))  # type: ignore[arg-type]
        .where(Form.id == form_id)
    ).first()

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    return build_form_public(form)


@router.put(
    "/{form_id}",
    response_model=FormPublic,
    dependencies=[Depends(permission_dependency("update_form"))],
)
def update_form(
    form_id: int,
    form_update: FormUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> FormPublic:
    """Update a form's metadata."""
    form = session.exec(
        select(Form)
        .options(selectinload(Form.fields))  # type: ignore[arg-type]
        .where(Form.id == form_id)
    ).first()

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    # Check for duplicate name if name is being updated
    if form_update.name and form_update.name != form.name:
        normalized_name = form_update.name.strip().lower()
        existing = session.exec(
            select(Form)
            .where(func.lower(func.trim(Form.name)) == normalized_name)
            .where(Form.organization_id == current_user.organization_id)
            .where(Form.id != form_id)
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Form with name '{form_update.name}' already exists.",
            )

    update_data = form_update.model_dump(exclude_unset=True)
    form.sqlmodel_update(update_data)

    session.add(form)
    session.commit()
    session.refresh(form)

    return build_form_public(form)


@router.delete(
    "/{form_id}",
    dependencies=[Depends(permission_dependency("delete_form"))],
)
def delete_form(
    form_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete a form."""
    form = session.get(Form, form_id)

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    # Check if form is associated with any tests
    if form.tests:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete form because it is associated with tests. Remove the form from all tests first.",
        )

    # Check if form has any responses
    has_responses = session.exec(
        select(FormResponse).where(FormResponse.form_id == form_id)
    ).first()

    if has_responses:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete form because it has submitted responses.",
        )

    session.delete(form)
    session.commit()

    return Message(message="Form deleted successfully")


# ============== FormField Management Endpoints ==============


@router.post(
    "/{form_id}/field/",
    response_model=FormFieldPublic,
    dependencies=[Depends(permission_dependency("update_form"))],
)
def add_field_to_form(
    form_id: int,
    field_create: FormFieldCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> FormFieldPublic:
    """Add a new field to a form."""
    form = session.get(Form, form_id)

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    # Check for duplicate field name within form
    existing_field = session.exec(
        select(FormField)
        .where(FormField.form_id == form_id)
        .where(func.lower(FormField.name) == field_create.name.lower())
    ).first()

    if existing_field:
        raise HTTPException(
            status_code=400,
            detail=f"Field with name '{field_create.name}' already exists in this form.",
        )

    # Get max order to append at end
    max_order_result = session.exec(
        select(func.max(FormField.order)).where(FormField.form_id == form_id)
    ).first()
    next_order = (max_order_result or 0) + 1

    # Determine field order: use provided order if > 0, otherwise append at end
    field_order = field_create.order if field_create.order > 0 else next_order

    field = FormField(
        **field_create.model_dump(exclude={"order"}),
        form_id=form_id,
        order=field_order,
    )

    session.add(field)
    session.commit()
    session.refresh(field)

    return FormFieldPublic(**field.model_dump())


@router.get(
    "/{form_id}/field/",
    response_model=list[FormFieldPublic],
    dependencies=[Depends(permission_dependency("read_form"))],
)
def get_form_fields(
    form_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[FormFieldPublic]:
    """Get all fields for a form."""
    form = session.get(Form, form_id)

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    fields = session.exec(
        select(FormField).where(FormField.form_id == form_id).order_by(FormField.order)  # type: ignore[arg-type]
    ).all()

    return [FormFieldPublic(**field.model_dump()) for field in fields]


@router.put(
    "/{form_id}/field/reorder",
    response_model=list[FormFieldPublic],
    dependencies=[Depends(permission_dependency("update_form"))],
)
def reorder_form_fields(
    form_id: int,
    reorder: FormFieldReorder,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[FormFieldPublic]:
    """Reorder form fields."""
    form = session.get(Form, form_id)

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    # Get all fields for this form
    fields = session.exec(select(FormField).where(FormField.form_id == form_id)).all()

    field_map = {field.id: field for field in fields}

    # Validate all field IDs belong to this form
    for field_id in reorder.field_ids:
        if field_id not in field_map:
            raise HTTPException(
                status_code=400,
                detail=f"Field ID {field_id} does not belong to this form.",
            )

    # Update order based on position in the list
    for index, field_id in enumerate(reorder.field_ids):
        field = field_map[field_id]
        field.order = index
        session.add(field)

    session.commit()

    # Return updated fields in order
    updated_fields = session.exec(
        select(FormField).where(FormField.form_id == form_id).order_by(FormField.order)  # type: ignore[arg-type]
    ).all()

    return [FormFieldPublic(**field.model_dump()) for field in updated_fields]


@router.put(
    "/{form_id}/field/{field_id}",
    response_model=FormFieldPublic,
    dependencies=[Depends(permission_dependency("update_form"))],
)
def update_form_field(
    form_id: int,
    field_id: int,
    field_update: FormFieldUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> FormFieldPublic:
    """Update a form field."""
    form = session.get(Form, form_id)

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    field = session.exec(
        select(FormField)
        .where(FormField.id == field_id)
        .where(FormField.form_id == form_id)
    ).first()

    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    # Check for duplicate name if name is being updated
    if field_update.name and field_update.name.lower() != field.name.lower():
        existing = session.exec(
            select(FormField)
            .where(FormField.form_id == form_id)
            .where(func.lower(FormField.name) == field_update.name.lower())
            .where(FormField.id != field_id)
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Field with name '{field_update.name}' already exists in this form.",
            )

    update_data = field_update.model_dump(exclude_unset=True)
    field.sqlmodel_update(update_data)

    session.add(field)
    session.commit()
    session.refresh(field)

    return FormFieldPublic(**field.model_dump())


@router.delete(
    "/{form_id}/field/{field_id}",
    dependencies=[Depends(permission_dependency("update_form"))],
)
def delete_form_field(
    form_id: int,
    field_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """Delete a form field."""
    form = session.get(Form, form_id)

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    field = session.exec(
        select(FormField)
        .where(FormField.id == field_id)
        .where(FormField.form_id == form_id)
    ).first()

    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    session.delete(field)
    session.commit()

    return Message(message="Field deleted successfully")


# ============== Form Response Endpoints ==============


@router.get(
    "/{form_id}/responses",
    response_model=Page[FormResponsePublic],
    dependencies=[Depends(permission_dependency("read_form_response"))],
)
def get_form_responses(
    form_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
) -> Page[FormResponsePublic]:
    """Get all responses for a form."""
    form = session.get(Form, form_id)

    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form not found")

    query = (
        select(FormResponse)
        .where(FormResponse.form_id == form_id)
        .order_by(FormResponse.created_date.desc())  # type: ignore[union-attr]
    )

    responses: Page[FormResponsePublic] = paginate(
        session,
        query,  # type: ignore[arg-type]
        params,
        transformer=lambda items: [
            FormResponsePublic(**item.model_dump()) for item in items
        ],
    )

    return responses


@router.get(
    "/response/{candidate_test_id}",
    response_model=FormResponsePublic,
    dependencies=[Depends(permission_dependency("read_form_response"))],
)
def get_form_response_by_candidate_test(
    candidate_test_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> FormResponsePublic:
    """Get form response for a specific candidate test."""
    response = session.exec(
        select(FormResponse).where(FormResponse.candidate_test_id == candidate_test_id)
    ).first()

    if not response:
        raise HTTPException(status_code=404, detail="Form response not found")

    # Verify user has access to this response via form's organization
    form = session.get(Form, response.form_id)
    if not form or form.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Form response not found")

    return FormResponsePublic(**response.model_dump())
