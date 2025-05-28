import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlmodel import SQLModel, not_, select

from app.api.deps import SessionDep, permission_dependency
from app.models import (
    Candidate,
    CandidateCreate,
    CandidatePublic,
    CandidateTest,
    CandidateTestAnswer,
    CandidateTestAnswerCreate,
    CandidateTestAnswerPublic,
    CandidateTestAnswerUpdate,
    CandidateTestCreate,
    CandidateTestPublic,
    CandidateTestUpdate,
    CandidateUpdate,
    Message,
    QuestionCandidatePublic,
    QuestionRevision,
    Test,
    TestCandidatePublic,
    TestQuestion,
)

router = APIRouter(prefix="/candidate", tags=["Candidate"])
router_candidate_test = APIRouter(prefix="/candidate_test", tags=["Candidate Test"])
router_candidate_test_answer = APIRouter(
    prefix="/candidate_test_answer", tags=["Candidate-Test Answer"]
)


# Simple request/response models for start_test
class StartTestRequest(SQLModel):
    test_id: int
    device_info: str | None = None


class StartTestResponse(SQLModel):
    candidate_uuid: uuid.UUID
    candidate_test_id: int


@router.post("/start_test", response_model=StartTestResponse)
def start_test_for_candidate(
    session: SessionDep,
    start_test_request: StartTestRequest = Body(...),
) -> StartTestResponse:
    """
    Creates a candidate when they start a test, links them to the test.
    Returns the candidate UUID for verification.
    """
    # Find the test by ID
    test = session.get(Test, start_test_request.test_id)
    if not test or test.is_deleted or (test.is_active is False):
        raise HTTPException(status_code=404, detail="Test not found or not active")

    # Create a new anonymous candidate with UUID
    candidate = Candidate(
        identity=uuid.uuid4(),  # Generate UUID for anonymous candidate
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)

    # Set start_time when test begins, end_time will be set when test is submitted
    start_time = datetime.now(timezone.utc)

    # Create CandidateTest link
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=start_test_request.device_info or "unknown",
        consent=True,
        start_time=start_time,
        end_time=None,  # Will be set when test is actually submitted
        is_submitted=False,
    )
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)

    return StartTestResponse(
        candidate_uuid=candidate.identity,
        candidate_test_id=candidate_test.id,
    )


# Get test questions after verification
@router.get("/test_questions/{candidate_test_id}", response_model=TestCandidatePublic)
def get_test_questions(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> TestCandidatePublic:
    """
    Get test questions for a candidate test, verified by candidate UUID.
    """
    # Verify candidate_test belongs to the candidate with given UUID
    candidate_test_statement = (
        select(CandidateTest)
        .join(Candidate)
        .where(CandidateTest.id == candidate_test_id)
        .where(Candidate.identity == candidate_uuid)
    )
    candidate_test = session.exec(candidate_test_statement).first()

    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="Candidate test not found or invalid UUID"
        )

    # Get the full test with all relationships
    test = session.get(Test, candidate_test.test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    from app.models.location import State
    from app.models.tag import Tag
    from app.models.test import TestState, TestTag

    tags_query = select(Tag).join(TestTag).where(TestTag.test_id == test.id)
    tags = session.exec(tags_query).all()

    question_revision_query = (
        select(QuestionRevision)
        .join(TestQuestion)
        .where(TestQuestion.test_id == test.id)
    )
    question_revisions = session.exec(question_revision_query).all()

    state_query = select(State).join(TestState).where(TestState.test_id == test.id)
    states = session.exec(state_query).all()

    # Convert questions to candidate-safe format (no answers)
    candidate_questions = [
        QuestionCandidatePublic(
            id=q.id,
            question_text=q.question_text,
            instructions=q.instructions,
            question_type=q.question_type,
            options=q.options,
            subjective_answer_limit=q.subjective_answer_limit,
            is_mandatory=q.is_mandatory,
            media=q.media,
        )
        for q in question_revisions
    ]

    return TestCandidatePublic(
        **test.model_dump(),
        question_revisions=candidate_questions,
        tags=tags,
        states=states,
        total_questions=len(question_revisions),
        candidate_test=candidate_test,
    )


# Create a Candidate
@router.post(
    "/",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("create_candidate"))],
)
def create_candidate(
    candidate_create: CandidateCreate, session: SessionDep
) -> Candidate:
    candidate = Candidate.model_validate(candidate_create)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Get all Candidates
@router.get(
    "/",
    response_model=list[CandidatePublic],
    dependencies=[Depends(permission_dependency("read_candidate"))],
)
def get_candidate(session: SessionDep) -> Sequence[Candidate]:
    candidate = session.exec(select(Candidate).where(not_(Candidate.is_deleted))).all()
    return candidate


# Get Candidate by ID
@router.get(
    "/{candidate_id}",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("read_candidate"))],
)
def get_candidate_by_id(candidate_id: int, session: SessionDep) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


# Update a Candidate
@router.put(
    "/{candidate_id}",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("update_candidate"))],
)
def update_candidate(
    candidate_id: int,
    updated_data: CandidateUpdate,
    session: SessionDep,
) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate_data = updated_data.model_dump(exclude_unset=True)
    candidate.sqlmodel_update(candidate_data)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Set Visibility of Candidate
@router.patch(
    "/{candidate_id}",
    response_model=CandidatePublic,
    dependencies=[Depends(permission_dependency("update_candidate"))],
)
def visibility_candidate(
    candidate_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of candidate"),
) -> Candidate:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.is_active = is_active
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


# Delete a Candidate
@router.delete(
    "/{candidate_id}",
    dependencies=[Depends(permission_dependency("delete_candidate"))],
)
def delete_candidate(candidate_id: int, session: SessionDep) -> Message:
    candidate = session.get(Candidate, candidate_id)
    if not candidate or candidate.is_deleted is True:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.is_deleted = True
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return Message(message="Candidate deleted successfully")


# Create Link between Candidate and Test


# Create a Candidate-Test Link
@router_candidate_test.post(
    "/",
    response_model=CandidateTestPublic,
    dependencies=[Depends(permission_dependency("create_candidate_test"))],
)
def create_candidate_test(
    candidate_test_create: CandidateTestCreate, session: SessionDep
) -> CandidateTest:
    candidate_test = CandidateTest.model_validate(candidate_test_create)
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)
    return candidate_test


# Get all Candidate-Test Link
@router_candidate_test.get(
    "/",
    response_model=list[CandidateTestPublic],
    dependencies=[Depends(permission_dependency("read_candidate_test"))],
)
def get_candidate_test(session: SessionDep) -> Sequence[CandidateTest]:
    candidate_test = session.exec(select(CandidateTest)).all()
    return candidate_test


# Get Candidate-Test Link by ID
@router_candidate_test.get(
    "/{candidate_test_id}",
    response_model=CandidateTestPublic,
    dependencies=[Depends(permission_dependency("read_candidate_test"))],
)
def get_candidate_test_by_id(
    candidate_test_id: int, session: SessionDep
) -> CandidateTest:
    candidate_test = session.get(CandidateTest, candidate_test_id)
    if not candidate_test:
        raise HTTPException(
            status_code=404, detail="No combination of candidate and test found"
        )
    return candidate_test


# Update Candidate-Test Link
@router_candidate_test.put(
    "/{candidate_test_id}",
    response_model=CandidateTestPublic,
    dependencies=[Depends(permission_dependency("update_candidate_test"))],
)
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


# Route for Answering a Question for a test by a candidate


# Create a Candidate-Test & Answers Link
@router_candidate_test_answer.post(
    "/",
    response_model=CandidateTestAnswerPublic,
    dependencies=[Depends(permission_dependency("create_candidate_test_answer"))],
)
def create_candidate_test_answer(
    candidate_test_answer_create: CandidateTestAnswerCreate, session: SessionDep
) -> CandidateTestAnswer:
    candidate_test_answer = CandidateTestAnswer.model_validate(
        candidate_test_answer_create
    )
    session.add(candidate_test_answer)
    session.commit()
    session.refresh(candidate_test_answer)
    return candidate_test_answer


# Get all Candidate-Test  & Answer Link
@router_candidate_test_answer.get(
    "/",
    response_model=list[CandidateTestAnswerPublic],
    dependencies=[Depends(permission_dependency("read_candidate_test_answer"))],
)
def get_candidate_test_answer(session: SessionDep) -> Sequence[CandidateTestAnswer]:
    candidate_test_answer = session.exec(select(CandidateTestAnswer)).all()
    return candidate_test_answer


# Get Candidate-Test  & Answer Link by ID
@router_candidate_test_answer.get(
    "/{candidate_test_answer_id}",
    response_model=CandidateTestAnswerPublic,
    dependencies=[Depends(permission_dependency("read_candidate_test_answer"))],
)
def get_candidate_test_answer_by_id(
    candidate_test_answer_id: int, session: SessionDep
) -> CandidateTestAnswer:
    candidate_test_answer = session.get(CandidateTestAnswer, candidate_test_answer_id)
    if not candidate_test_answer:
        raise HTTPException(
            status_code=404,
            detail="No Answer found",
        )
    return candidate_test_answer


# Update Candidate-Test & Answer Link
@router_candidate_test_answer.put(
    "/{candidate_test_answer_id}",
    response_model=CandidateTestAnswerPublic,
    dependencies=[Depends(permission_dependency("update_candidate_test_answer"))],
)
def update_candidate_answer_test(
    candidate_test_answer_id: int,
    updated_data: CandidateTestAnswerUpdate,
    session: SessionDep,
) -> CandidateTestAnswer:
    candidate_test_answer = session.get(CandidateTestAnswer, candidate_test_answer_id)
    if not candidate_test_answer:
        raise HTTPException(status_code=404, detail="No Answer found")

    candidate_test_answer_data = updated_data.model_dump(exclude_unset=True)
    candidate_test_answer.sqlmodel_update(candidate_test_answer_data)
    session.add(candidate_test_answer)
    session.commit()
    session.refresh(candidate_test_answer)
    return candidate_test_answer
