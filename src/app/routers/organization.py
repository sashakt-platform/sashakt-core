from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.organization import Organization


router = APIRouter(prefix="/organization", tags=["Organization"])


# Create a Organization
@router.post("/", response_model=Organization)
def create_organization(
    organization: Organization, session: Session = Depends(get_session)
):
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


# Get all Organizations
@router.get("/", response_model=list[Organization])
def get_organization(session: Session = Depends(get_session)):
    organization = session.exec(select(Organization)).all()
    return organization


# Get Organization by ID
@router.get("/{organization_id}", response_model=Organization)
def get_organization_by_id(
    organization_id: int, session: Session = Depends(get_session)
):
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


# Update a Organization
@router.put("/{organization_id}", response_model=Organization)
def update_organization(
    organization_id: int,
    updated_data: Organization,
    session: Session = Depends(get_session),
):
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.name = updated_data.name
    organization.description = updated_data.description
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization
