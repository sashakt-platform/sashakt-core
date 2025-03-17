from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.models.candidate import (
    Candidate,
    CandidateCreate,
    CandidatePublic,
    CandidateUpdate,
)

router = APIRouter(prefix="/candidate", tags=["Candidate"])


# Create a Candidate
@router.post("/", response_model=CandidatePublic)
def create_candidate(
    candidate_create: CandidateCreate, session: SessionDep
) -> Candidate:
    candidate = Candidate.model_validate(candidate_create)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Get all Candidates
@router.get("/", response_model=list[CandidatePublic])
def get_candidate(session: SessionDep) -> Sequence[Candidate]:
    candidate = session.exec(
        select(Candidate).where(Candidate.is_deleted is not False)
    ).all()
    return candidate


# Get Candidate by ID
@router.get("/{candidate_id}", response_model=CandidatePublic)
def get_candidate_by_id(candidate_id: int, session: SessionDep) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


# Update a Candidate
@router.put("/{candidate_id}", response_model=CandidatePublic)
def update_candidate(
    candidate_id: int,
    updated_data: CandidateUpdate,
    session: SessionDep,
) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate_data = updated_data.model_dump(exclude_unset=True)
    candidate.sqlmodel_update(candidate_data)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Set Visibility of Candidate
@router.patch("/{candidate_id}", response_model=CandidatePublic)
def visibility_candidate(
    candidate_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of candidate"),
) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.is_active = is_active
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Delete a Candidate
@router.delete("/{candidate_id}", response_model=CandidatePublic)
def delete_candidate(candidate_id: int, session: SessionDep) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.is_deleted = True
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate
