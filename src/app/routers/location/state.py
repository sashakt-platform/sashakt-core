from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.location import State

router = APIRouter()


# Create a State
@router.post("/", response_model=State)
def create_state(state: State, session: Session = Depends(get_session)):
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


# Get all States
@router.get("/", response_model=list[State])
def get_state(session: Session = Depends(get_session)):
    states = session.exec(select(State)).all()
    return states


# Get State by ID
@router.get("/{state_id}", response_model=State)
def get_state_by_id(state_id: int, session: Session = Depends(get_session)):
    state = session.get(State, state_id)
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    return state


# Update a State
@router.put("/{state_id}", response_model=State)
def update_state(
    state_id: int, updated_data: State, session: Session = Depends(get_session)
):
    state = session.get(State, state_id)
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    state.name = updated_data.name
    session.add(state)
    session.commit()
    session.refresh(state)
    return state
