from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models.location import (
    Country,
    CountryCreate,
    CountryPublic,
    CountryUpdate,
)

router = APIRouter()


# Create a Country
@router.post("/", response_model=CountryPublic)
def create_country(country: CountryCreate, session: Session = Depends(get_session)):
    db_country = Country.model_validate(country)
    session.add(db_country)
    session.commit()
    session.refresh(db_country)
    return db_country


# Get all Countries
@router.get("/", response_model=list[CountryPublic])
def get_countries(
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: Annotated[int, Query(le=10)] = 10,
):
    countries = session.exec(select(Country).offset(offset).limit(limit)).all()
    return countries


# Get Country by ID
@router.get("/{country_id}", response_model=CountryPublic)
def get_country_by_id(country_id: int, session: Session = Depends(get_session)):
    country = session.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


# Update a Country
@router.put("/{country_id}", response_model=CountryPublic)
def update_country(
    country_id: int, country: CountryUpdate, session: Session = Depends(get_session)
):
    country_db = session.get(Country, country_id)
    if not country_db:
        raise HTTPException(status_code=404, detail="Country not found")
    country_data = country.model_dump(exclude_unset=True)
    country_db.sqlmodel_update(country_data)
    session.add(country_db)
    session.commit()
    session.refresh(country_db)
    return country_db
