from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, permission_dependency
from app.core.permissions import manage_organization
from app.models import (
    Block,
    BlockCreate,
    BlockPublic,
    BlockUpdate,
    Country,
    CountryCreate,
    CountryPublic,
    CountryUpdate,
    District,
    DistrictCreate,
    DistrictPublic,
    DistrictUpdate,
    State,
    StateCreate,
    StatePublic,
    StateUpdate,
)

router = APIRouter(prefix="/location", tags=["Location"])

country_router = APIRouter()
state_router = APIRouter()
district_router = APIRouter()
block_router = APIRouter()


# Create a Country
@country_router.post(
    "/",
    response_model=CountryPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def create_country(
    country: CountryCreate,
    session: SessionDep,
) -> Country:
    db_country = Country.model_validate(country)
    session.add(db_country)
    session.commit()
    session.refresh(db_country)
    return db_country


# Get all Countries
@country_router.get(
    "/",
    response_model=list[CountryPublic],
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_countries(
    session: SessionDep,
) -> Sequence[Country]:
    countries = session.exec(select(Country)).all()
    return countries


# Get Country by ID
@country_router.get(
    "/{country_id}",
    response_model=CountryPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_country_by_id(
    country_id: int,
    session: SessionDep,
) -> Country:
    country = session.get(Country, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


# Update a Country
@country_router.put(
    "/{country_id}",
    response_model=CountryPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def update_country(
    country_id: int,
    country: CountryUpdate,
    session: SessionDep,
) -> Country:
    country_db = session.get(Country, country_id)
    if not country_db:
        raise HTTPException(status_code=404, detail="Country not found")
    country_data = country.model_dump(exclude_unset=True)
    country_db.sqlmodel_update(country_data)
    session.add(country_db)
    session.commit()
    session.refresh(country_db)
    return country_db


# ------- State Level Routes ------


# Create a State
@state_router.post(
    "/",
    response_model=StatePublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def create_state(
    *,
    state_create: StateCreate,
    session: SessionDep,
) -> Any:
    state = State.model_validate(state_create)
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


# Get all States
@state_router.get(
    "/",
    response_model=list[StatePublic],
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_state(
    session: SessionDep,
) -> Sequence[State]:
    states = session.exec(select(State)).all()
    return states


# Get State by ID
@state_router.get(
    "/{state_id}",
    response_model=StatePublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_state_by_id(
    state_id: int,
    session: SessionDep,
) -> State:
    state = session.get(State, state_id)
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    return state


# Update State by ID
@state_router.put(
    "/{state_id}",
    response_model=StatePublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def update_state(
    *,
    state_id: int,
    state_update: StateUpdate,
    session: SessionDep,
) -> Any:
    state_db = session.get(State, state_id)
    if not state_db:
        raise HTTPException(status_code=404, detail="State not found")
    state_data = state_update.model_dump(exclude_unset=True)
    state_db.sqlmodel_update(state_data)
    session.add(state_db)
    session.commit()
    session.refresh(state_db)
    return state_db


#  -------- District Level Routes ------


# Create a District
@district_router.post(
    "/",
    response_model=DistrictPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def create_district(
    *,
    district_create: DistrictCreate,
    session: SessionDep,
) -> Any:
    district = District.model_validate(district_create)
    session.add(district)
    session.commit()
    session.refresh(district)
    return district


# Get all Districts
@district_router.get(
    "/",
    response_model=list[DistrictPublic],
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_district(
    session: SessionDep,
) -> Sequence[District]:
    districts = session.exec(select(District)).all()
    return districts


# Get District by ID
@district_router.get(
    "/{district_id}",
    response_model=DistrictPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_district_by_id(
    district_id: int,
    session: SessionDep,
) -> District:
    district = session.get(District, district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    return district


# Update District by ID
@district_router.put(
    "/{district_id}",
    response_model=DistrictPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def update_district(
    *,
    district_id: int,
    district_update: DistrictUpdate,
    session: SessionDep,
) -> District:
    district_db = session.get(District, district_id)
    if not district_db:
        raise HTTPException(status_code=404, detail="District not found")
    district_data = district_update.model_dump(exclude_unset=True)
    district_db.sqlmodel_update(district_data)
    session.add(district_db)
    session.commit()
    session.refresh(district_db)
    return district_db


#  -------- Block Level Routes ------


# Create a Block
@block_router.post(
    "/",
    response_model=BlockPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def create_block(
    *,
    block_create: BlockCreate,
    session: SessionDep,
) -> Any:
    block = Block.model_validate(block_create)
    session.add(block)
    session.commit()
    session.refresh(block)
    return block


# Get all Blocks
@block_router.get(
    "/",
    response_model=list[BlockPublic],
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_block(
    session: SessionDep,
) -> Sequence[Block]:
    blocks = session.exec(select(Block)).all()
    return blocks


# Get Block by ID
@block_router.get(
    "/{block_id}",
    response_model=BlockPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def get_block_by_id(
    block_id: int,
    session: SessionDep,
) -> Block:
    block = session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block


# Update Block by ID
@block_router.put(
    "/{block_id}",
    response_model=BlockPublic,
    dependencies=[Depends(permission_dependency(manage_organization.name))],
)
def update_block(
    *,
    block_id: int,
    block_update: BlockUpdate,
    session: SessionDep,
) -> Block:
    block_db = session.get(Block, block_id)
    if not block_db:
        raise HTTPException(status_code=404, detail="Block not found")
    block_data = block_update.model_dump(exclude_unset=True)
    block_db.sqlmodel_update(block_data)
    session.add(block_db)
    session.commit()
    session.refresh(block_db)
    return block_db


# Include all routers
router.include_router(country_router, prefix="/country", tags=["Country"])
router.include_router(state_router, prefix="/state", tags=["State"])
router.include_router(district_router, prefix="/district", tags=["District"])
router.include_router(block_router, prefix="/block", tags=["Block"])
