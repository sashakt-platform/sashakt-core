from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationPublic,
    OrganizationUpdate,
)

router = APIRouter(prefix="/organization", tags=["Organization"])


# Create a Organization
@router.post("/", response_model=OrganizationPublic)
def create_organization(
    organization_create: OrganizationCreate, session: Session = Depends(get_session)
):
    organization = Organization.model_validate(organization_create)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Get all Organizations
@router.get("/", response_model=list[OrganizationPublic])
def get_organization(session: Session = Depends(get_session)):
    organization = session.exec(select(Organization)).all()
    return organization


# Get Organization by ID
@router.get("/{organization_id}", response_model=OrganizationPublic)
def get_organization_by_id(
    organization_id: int, session: Session = Depends(get_session)
):
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


# Update a Organization
@router.put("/{organization_id}", response_model=OrganizationPublic)
def update_organization(
    organization_id: int,
    updated_data: OrganizationUpdate,
    session: Session = Depends(get_session),
):
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
    is_active: bool = Query(False, description="Set visibility of organization"),
    session: Session = Depends(get_session),
):
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.is_active = is_active
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Delete a Organization
@router.delete("/{organization_id}", response_model=OrganizationPublic)
def delete_organization(organization_id: int, session: Session = Depends(get_session)):
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.is_deleted = True
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization
