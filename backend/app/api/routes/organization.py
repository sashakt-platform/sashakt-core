from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.models import (
    Message,
    Organization,
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
)

router = APIRouter(prefix="/organization", tags=["Organization"])


# Create a Organization
@router.post("/", response_model=OrganizationPublic)
def create_organization(
    organization_create: OrganizationCreate, session: SessionDep
) -> Organization:
    organization = Organization.model_validate(organization_create)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Get all Organizations
@router.get("/", response_model=list[OrganizationPublic])
def get_organization(session: SessionDep) -> Sequence[Organization]:
    organization = session.exec(select(Organization)).all()
    return organization


# Get Organization by ID
@router.get("/{organization_id}", response_model=OrganizationPublic)
def get_organization_by_id(organization_id: int, session: SessionDep) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization or organization.is_deleted is True:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


# Update a Organization
@router.put("/{organization_id}", response_model=OrganizationPublic)
def update_organization(
    organization_id: int,
    updated_data: OrganizationUpdate,
    session: SessionDep,
) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization_data = updated_data.model_dump(exclude_unset=True)
    organization.sqlmodel_update(organization_data)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Set Visibility of Organization
@router.patch("/{organization_id}", response_model=OrganizationPublic)
def visibility_organization(
    organization_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of organization"),
) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.is_active = is_active
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Delete a Organization
@router.delete("/{organization_id}", response_model=Message)
def delete_organization(organization_id: int, session: SessionDep) -> Organization:
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.is_deleted = True
    session.add(organization)
    session.commit()
    session.refresh(organization)

    return Message(message="Organization deleted successfully")
