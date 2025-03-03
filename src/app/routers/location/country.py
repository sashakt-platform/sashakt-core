from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.location import Country

router = APIRouter()


# Create a Country
@router.post("/", response_model=Country)
def create_country(country: Country, session: Session = Depends(get_session)):
    session.add(country)
    session.commit()
    session.refresh(country)
    return country


# Get all Countries
@router.get("/", response_model=list[Country])
def get_countries(session: Session = Depends(get_session)):
    countries = session.exec(select(Country)).all()
    return countries


# Get Country by ID
@router.get("/{country_id}", response_model=Country)
def get_country_by_id(country_id: int, session: Session = Depends(get_session)):
    country = session.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


# Update a Country
@router.put("/{country_id}", response_model=Country)
def update_country(
    country_id: int, updated_data: Country, session: Session = Depends(get_session)
):
    country = session.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    country.name = updated_data.name
    session.add(country)
    session.commit()
    session.refresh(country)
    return country
