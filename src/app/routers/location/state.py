from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.location import State, StateCreate, StatePublic, StateUpdate

router = APIRouter()


# Create a State
@router.post("/", response_model=StatePublic)
def create_state(
    *,
    state_create: StateCreate,
    session: Session = Depends(get_session),
) -> Any:
    state = State.model_validate(state_create)
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


# Get all States
@router.get("/", response_model=list[StatePublic])
def get_state(session: Session = Depends(get_session)):
    states = session.exec(select(State)).all()
    return states


# Get State by ID
@router.get("/{state_id}", response_model=StatePublic)
def get_state_by_id(state_id: int, session: Session = Depends(get_session)):
    state = session.get(State, state_id)
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    return state


# Update State by ID
@router.put("/{state_id}", response_model=StatePublic)
def update_state(
    *,
    state_id: int,
    state_update: StateUpdate,
    session: Session = Depends(get_session),
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
