from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import col, func, not_, select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.core.config import PAGINATION_SIZE
from app.models import (
    Message,
    Organization,
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
)
from app.models.organization import AggregatedData
from app.models.question import Question
from app.models.test import Test
from app.models.user import User

router = APIRouter(prefix="/organization", tags=["Organization"])


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
    response_model=list[OrganizationPublic],
    dependencies=[Depends(permission_dependency("read_organization"))],
)
def get_organization(
    session: SessionDep,
    skip: int = Query(0, description="Number of rows to skip"),
    limit: int = Query(
        PAGINATION_SIZE, description="Maximum number of entries to return"
    ),
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
) -> Sequence[Organization]:
    query = select(Organization).where(not_(Organization.is_deleted))

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

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query and get all organization
    organization = session.exec(query).all()

    return organization


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

    total_questions = session.exec(
        select(func.count()).where(
            not_(Question.is_deleted), Question.organization_id == organization_id
        )
    ).one()

    total_users = session.exec(
        select(func.count()).where(
            User.organization_id == organization_id, not_(User.is_deleted)
        )
    ).one()

    query = (
        select(func.count())
        .select_from(Test)
        .join(User)
        .where(
            Test.created_by_id == User.id,
            not_(Test.is_deleted),
            not_(Test.is_template),
        )
        .where(
            User.organization_id == current_user.organization_id,
        )
    )

    total_tests = session.exec(query).one()
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
