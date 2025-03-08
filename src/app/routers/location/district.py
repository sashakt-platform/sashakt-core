from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.location import (
    District,
    DistrictCreate,
    DistrictPublic,
    DistrictUpdate,
)

router = APIRouter()


# Create a District
@router.post("/", response_model=DistrictPublic)
def create_district(
    *,
    district_create: DistrictCreate,
    session: Session = Depends(get_session),
) -> Any:
    district = District.model_validate(district_create)
    session.add(district)
    session.commit()
    session.refresh(district)
    return district


# Get all Districts
@router.get("/", response_model=list[DistrictPublic])
def get_district(session: Session = Depends(get_session)):
    districts = session.exec(select(District)).all()
    return districts


# Get District by ID
@router.get("/{district_id}", response_model=DistrictPublic)
def get_district_by_id(district_id: int, session: Session = Depends(get_session)):
    district = session.get(District, district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    return district


# Update District by ID
@router.put("/{district_id}", response_model=DistrictPublic)
def update_district(
    *,
    district_id: int,
    district_update: DistrictUpdate,
    session: Session = Depends(get_session),
) -> Any:
    district_db = session.get(District, district_id)
    if not district_db:
        raise HTTPException(status_code=404, detail="District not found")
    district_data = district_update.model_dump(exclude_unset=True)
    district_db.sqlmodel_update(district_data)
    session.add(district_db)
    session.commit()
    session.refresh(district_db)
    return district_db
