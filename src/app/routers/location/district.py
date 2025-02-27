from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.location import District


router = APIRouter()


# Create a District
@router.post("/", response_model=District)
def create_district(district: District, session: Session = Depends(get_session)):
    session.add(district)
    session.commit()
    session.refresh(district)
    return district


# Get all Districts
@router.get("/", response_model=list[District])
def get_district(session: Session = Depends(get_session)):
    districts = session.exec(select(District)).all()
    return districts


# Get District by ID
@router.get("/{district_id}", response_model=District)
def get_district_by_id(district_id: int, session: Session = Depends(get_session)):
    district = session.get(District, district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    return district


# Update a District
@router.put("/{district_id}", response_model=District)
def update_district(
    district_id: int, updated_data: District, session: Session = Depends(get_session)
):
    district = session.get(District, district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    district.name = updated_data.name
    session.add(district)
    session.commit()
    session.refresh(district)
    return district
