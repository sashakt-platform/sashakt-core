from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.models import (
    Candidate,
    CandidateCreate,
    CandidatePublic,
    CandidateTest,
    CandidateTestCreate,
    CandidateTestPublic,
    CandidateTestUpdate,
    CandidateUpdate,
    Message,
)

router = APIRouter(prefix="/candidate", tags=["Candidate"])
router_candidate_test = APIRouter(prefix="/candidate_test", tags=["Candidate Test"])


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
@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, session: SessionDep) -> Message:
    candidate = session.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.is_deleted = True
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return Message(message="Candidate deleted successfully")


# Create Link between Candidate and Test


# Create a Candidate-Test Link
@router_candidate_test.post("/", response_model=CandidateTestPublic)
def create_candidate_test(
    candidate_test_create: CandidateTestCreate, session: SessionDep
) -> Candidate:
    candidate_test = CandidateTest.model_validate(candidate_test_create)
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)
    return candidate_test


# Get all Candidate-Test Link
@router_candidate_test.get("/", response_model=list[CandidateTestPublic])
def get_candidate_test(session: SessionDep) -> Sequence[CandidateTest]:
    candidate_test = session.exec(select(CandidateTest)).all()
    return candidate_test


# Get Candidate-Test Link by ID
@router_candidate_test.get("/{candidate_test_id}", response_model=CandidateTestPublic)
def get_organization_by_id(
    candidate_test_id: int, session: SessionDep
) -> CandidateTest:
    candidate_test = session.get(CandidateTest, candidate_test_id)
    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="No combination of candidate and test found"
        )
    return candidate_test


# Update Candidate-Test Link
@router_candidate_test.put("/{candidate_test_id}", response_model=CandidateTestPublic)
def update_candidate_test(
    candidate_test_id: int,
    updated_data: CandidateTestUpdate,
    session: SessionDep,
) -> CandidateTest:
    candidate_test = session.get(CandidateTest, candidate_test_id)
    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="No combination of candidate and test found"
        )

    candidate_test_data = updated_data.model_dump(exclude_unset=True)
    candidate_test.sqlmodel_update(candidate_test_data)
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)
    return candidate_test
