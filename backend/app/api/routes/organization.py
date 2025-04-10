from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import not_, select

from app.api.deps import SessionDep, permission_dependency
from app.models import (
    Message,
    Organization,
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
)

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
def get_organization(session: SessionDep) -> Sequence[Organization]:
    organization = session.exec(
        select(Organization).where(not_(Organization.is_deleted))
    ).all()
    return organization


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
