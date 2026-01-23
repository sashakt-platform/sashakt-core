from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlmodel import col, func, not_, or_, select

from app.api.deps import (
    CurrentUser,
    Pagination,
    SessionDep,
    get_current_user,
    permission_dependency,
)
from app.core.files import delete_logo_file, save_logo_file, validate_logo_upload
from app.core.roles import state_admin, test_admin
from app.models import (
    AggregatedData,
    Message,
    Organization,
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
    Question,
    Test,
    User,
)
from app.models.organization import OrganizationPublicMinimal
from app.models.question import QuestionLocation
from app.models.test import TestState
from app.models.user import UserState

router = APIRouter(prefix="/organization", tags=["Organization"])


def transform_organizations_to_public(
    items: list[Organization] | Any,
) -> list[OrganizationPublic]:
    result: list[OrganizationPublic] = []
    organization_list: list[Organization] = (
        list(items) if not isinstance(items, list) else items
    )

    for organization in organization_list:
        result.append(OrganizationPublic(**organization.model_dump()))

    return result


@router.get(
    "/current",
    response_model=OrganizationPublic,
    dependencies=[Depends(permission_dependency("read_organization"))],
)
def get_current_organization(
    current_user: User = Depends(get_current_user),
) -> OrganizationPublic:
    organization = current_user.organization

    return transform_organizations_to_public([organization])[0]


@router.patch(
    "/current",
    response_model=OrganizationPublic,
    dependencies=[Depends(permission_dependency("update_organization"))],
)
async def update_current_organization(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
    name: str | None = Form(None),
    shortcode: str | None = Form(None),
    logo: UploadFile | None = File(
        None, description="Organization logo (PNG, JPG, WebP, max 2MB)"
    ),
) -> OrganizationPublic:
    organization = current_user.organization

    old_logo_path = organization.logo
    new_logo_path = None

    # Handle logo upload if provided
    if logo is not None:
        file_content, file_ext = await validate_logo_upload(logo)
        new_logo_path = save_logo_file(organization.id, file_content, file_ext)

    # Build update dictionary from non-None parameters
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if shortcode is not None:
        update_data["shortcode"] = shortcode
    if new_logo_path is not None:
        update_data["logo"] = new_logo_path

    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    organization.sqlmodel_update(update_data)
    session.add(organization)

    # Commit to database and handle rollback if needed
    try:
        session.commit()
        session.refresh(organization)
    except Exception:
        # Rollback the database transaction
        session.rollback()
        # Clean up the newly uploaded file if it was saved
        if new_logo_path:
            delete_logo_file(new_logo_path)
        raise

    # Clean up old logo file if replaced (only after successful DB commit)
    if new_logo_path and old_logo_path and old_logo_path != new_logo_path:
        delete_logo_file(old_logo_path)

    return transform_organizations_to_public([organization])[0]


@router.delete(
    "/current/logo",
    response_model=OrganizationPublic,
    dependencies=[Depends(permission_dependency("update_organization"))],
)
async def delete_current_organization_logo(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> OrganizationPublic:
    organization = current_user.organization

    if not organization.logo:
        raise HTTPException(
            status_code=404,
            detail="Organization has no logo to delete",
        )

    old_logo_path = organization.logo
    organization.logo = None
    session.add(organization)
    session.commit()
    session.refresh(organization)
    delete_logo_file(old_logo_path)

    return transform_organizations_to_public([organization])[0]


# Create a Organization
@router.post(
    "/",
    response_model=OrganizationPublic,
    dependencies=[Depends(permission_dependency("create_organization"))],
)
def create_organization(
    organization_create: OrganizationCreate, session: SessionDep
) -> Organization:
    organization = Organization.model_validate(organization_create)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Get all Organizations
@router.get(
    "/",
    response_model=Page[OrganizationPublic],
    dependencies=[Depends(permission_dependency("read_organization"))],
)
def get_organization(
    session: SessionDep,
    params: Pagination = Depends(),
    name: str | None = Query(
        None,
        title="Filter by Name",
        description="Filter by organization name",
        min_length=3,
    ),
    description: str | None = Query(
        None, description="Filter by organization description", min_length=3
    ),
    order_by: list[str] = Query(
        default=["created_date"],
        title="Order by",
        description="Order by fields",
        examples=["-created_date", "name"],
    ),
) -> Page[OrganizationPublic]:
    query = select(Organization).where(
        not_(Organization.is_deleted),
        Organization.is_active == True,  # noqa: E712
    )

    if name:
        query = query.where(col(Organization.name).contains(name))

    if description:
        query = query.where(col(Organization.description).contains(description))

    for order in order_by:
        is_desc = order.startswith("-")
        order = order.lstrip("-")
        column = getattr(Organization, order, None)
        if column is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order_by field: {order}",
            )
        query = query.order_by(column.desc() if is_desc else column)

    organizations: Page[OrganizationPublic] = paginate(
        session,
        query,  # type: ignore[arg-type]
        params,
        transformer=lambda items: transform_organizations_to_public(items),
    )

    return organizations


@router.get(
    "/aggregated_data",
    response_model=AggregatedData,
    dependencies=[Depends(permission_dependency("read_organization"))],
)
def get_organization_aggregated_stats_for_current_user(
    session: SessionDep,
    current_user: CurrentUser,
) -> AggregatedData:
    organization_id = current_user.organization_id

    current_user_state_ids: list[int] = []
    if (
        current_user.role.name == state_admin.name
        or current_user.role.name == test_admin.name
    ):
        current_user_state_ids = (
            [state.id for state in current_user.states if state.id is not None]
            if current_user.states
            else []
        )

    questions_subquery = select(func.count(func.distinct(Question.id))).where(
        Question.organization_id == organization_id
    )

    if current_user_state_ids:
        questions_subquery = questions_subquery.outerjoin(QuestionLocation).where(
            or_(
                col(QuestionLocation.state_id).is_(None),
                col(QuestionLocation.state_id).in_(current_user_state_ids),
            )
        )

    users_subquery = select(func.count(func.distinct(User.id))).where(
        User.organization_id == organization_id
    )
    if current_user_state_ids:
        users_subquery = users_subquery.join(UserState).where(
            col(UserState.state_id).in_(current_user_state_ids)
        )

    tests_subquery = select(func.count(func.distinct(Test.id))).where(
        Test.organization_id == organization_id,
        not_(Test.is_template),
    )
    if current_user_state_ids:
        tests_subquery = tests_subquery.outerjoin(TestState).where(
            or_(
                col(TestState.state_id).is_(None),
                col(TestState.state_id).in_(current_user_state_ids),
            )
        )

    query = select(
        questions_subquery.scalar_subquery().label("total_questions"),
        users_subquery.scalar_subquery().label("total_users"),
        tests_subquery.scalar_subquery().label("total_tests"),
    )
    result = session.exec(query).one()

    total_questions, total_users, total_tests = cast(tuple[int, int, int], result)
    return AggregatedData(
        total_questions=total_questions,
        total_users=total_users,
        total_tests=total_tests,
    )


# Get Organization by ID
@router.get(
    "/{organization_id}",
    response_model=OrganizationPublic,
    dependencies=[Depends(permission_dependency("read_organization"))],
)
def get_organization_by_id(organization_id: int, session: SessionDep) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization or organization.is_deleted is True:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


# Update a Organization
@router.put(
    "/{organization_id}",
    response_model=OrganizationPublic,
    dependencies=[Depends(permission_dependency("update_organization"))],
)
def update_organization(
    organization_id: int,
    updated_data: OrganizationUpdate,
    session: SessionDep,
) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization or organization.is_deleted is True:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization_data = updated_data.model_dump(exclude_unset=True)
    organization.sqlmodel_update(organization_data)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Set Visibility of Organization
@router.patch(
    "/{organization_id}",
    response_model=OrganizationPublic,
    dependencies=[Depends(permission_dependency("update_organization"))],
)
def visibility_organization(
    organization_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of organization"),
) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization or organization.is_deleted is True:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.is_active = is_active
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Delete a Organization
@router.delete(
    "/{organization_id}",
    dependencies=[Depends(permission_dependency("delete_organization"))],
)
def delete_organization(organization_id: int, session: SessionDep) -> Message:
    organization = session.get(Organization, organization_id)
    if not organization or organization.is_deleted is True:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.is_deleted = True
    session.add(organization)
    session.commit()
    session.refresh(organization)

    return Message(message="Organization deleted successfully")


@router.get(
    "/public/{org_shortcode}",
    response_model=OrganizationPublicMinimal,
)
def get_public_organization_by_shortcode(
    org_shortcode: str,
    session: SessionDep,
) -> OrganizationPublicMinimal:
    organization = session.exec(
        select(Organization).where(
            Organization.shortcode == org_shortcode,
            col(Organization.is_deleted).is_(False),
            Organization.is_active,
        )
    ).first()

    if not organization:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return OrganizationPublicMinimal(
        name=organization.name,
        logo=organization.logo,
        shortcode=organization.shortcode,
    )
