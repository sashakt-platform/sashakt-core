import random
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlmodel import SQLModel, col, not_, select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.api.routes.utils import get_current_time
from app.core.timezone import get_timezone_aware_now
from app.models import (
    BatchAnswerSubmitRequest,
    Candidate,
    CandidateAnswerSubmitRequest,
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
from app.models.candidate import Result, TestStatusSummary
from app.models.user import User
from app.models.utils import TimeLeft

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
    question_revision_ids = [
        q.question_revision_id
        for q in session.exec(
            select(TestQuestion).where(TestQuestion.test_id == test.id)
        ).all()
    ]

    if test.random_questions and test.no_of_random_questions:
        question_revision_ids = random.sample(
            question_revision_ids,
            min(test.no_of_random_questions, len(question_revision_ids)),
        )
    if test.shuffle:
        random.shuffle(question_revision_ids)

    current_time = get_current_time()
    if test.start_time and test.start_time > current_time:
        raise HTTPException(
            status_code=400,
            detail="Test has not started yet. Please wait until the scheduled start time.",
        )

    # Create a new anonymous candidate with UUID
    candidate = Candidate(
        identity=uuid.uuid4(),  # Generate UUID for anonymous candidate
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)

    # Set start_time when test begins, end_time will be set when test is submitted
    start_time = get_timezone_aware_now()

    # Create CandidateTest link
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=start_test_request.device_info or "unknown",
        consent=True,
        start_time=start_time,
        end_time=None,  # Will be set when test is actually submitted
        is_submitted=False,
        question_revision_ids=question_revision_ids,
    )
    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)

    return StartTestResponse(
        candidate_uuid=candidate.identity,
        candidate_test_id=candidate_test.id,
    )


def verify_candidate_uuid_access(
    session: SessionDep, candidate_test_id: int, candidate_uuid: uuid.UUID
) -> CandidateTest:
    """Helper function to verify UUID-based access to candidate test."""
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
    return candidate_test


@router.post(
    "/submit_answer/{candidate_test_id}", response_model=CandidateTestAnswerPublic
)
def submit_answer_for_qr_candidate(
    candidate_test_id: int,
    session: SessionDep,
    answer_request: CandidateAnswerSubmitRequest = Body(...),
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> CandidateTestAnswer:
    """
    Submit answer for QR code candidates using UUID authentication.
    Creates new answer or updates existing one.
    """
    # Verify UUID access
    verify_candidate_uuid_access(session, candidate_test_id, candidate_uuid)

    # Check if answer already exists for this question
    existing_answer = session.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
        .where(
            CandidateTestAnswer.question_revision_id
            == answer_request.question_revision_id
        )
    ).first()

    if existing_answer:
        # Update existing answer
        existing_answer.response = answer_request.response
        existing_answer.visited = answer_request.visited
        existing_answer.time_spent = answer_request.time_spent
        session.add(existing_answer)
        session.commit()
        session.refresh(existing_answer)
        return existing_answer
    else:
        # Create new answer
        candidate_test_answer = CandidateTestAnswer(
            candidate_test_id=candidate_test_id,
            question_revision_id=answer_request.question_revision_id,
            response=answer_request.response,
            visited=answer_request.visited,
            time_spent=answer_request.time_spent,
        )
        session.add(candidate_test_answer)
        session.commit()
        session.refresh(candidate_test_answer)
        return candidate_test_answer


@router.post(
    "/submit_answers/{candidate_test_id}",
    response_model=list[CandidateTestAnswerPublic],
)
def submit_batch_answers_for_qr_candidate(
    candidate_test_id: int,
    session: SessionDep,
    batch_request: BatchAnswerSubmitRequest = Body(...),
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> list[CandidateTestAnswer]:
    """
    Submit multiple answers for QR code candidates using UUID authentication.
    Creates new answers or updates existing ones in a single transaction.
    """
    # Verify UUID access
    verify_candidate_uuid_access(session, candidate_test_id, candidate_uuid)

    results = []
    for answer in batch_request.answers:
        # Check if answer already exists for this question
        existing_answer = session.exec(
            select(CandidateTestAnswer)
            .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
            .where(
                CandidateTestAnswer.question_revision_id == answer.question_revision_id
            )
        ).first()

        if existing_answer:
            # Update existing answer
            existing_answer.response = answer.response
            existing_answer.visited = answer.visited
            existing_answer.time_spent = answer.time_spent
            session.add(existing_answer)
            results.append(existing_answer)
        else:
            # Create new answer
            new_answer = CandidateTestAnswer(
                candidate_test_id=candidate_test_id,
                question_revision_id=answer.question_revision_id,
                response=answer.response,
                visited=answer.visited,
                time_spent=answer.time_spent,
            )
            session.add(new_answer)
            results.append(new_answer)

    # Commit all changes in a single transaction
    session.commit()

    # Refresh all results
    for result in results:
        session.refresh(result)

    return results


@router.post("/submit_test/{candidate_test_id}", response_model=CandidateTestPublic)
def submit_test_for_qr_candidate(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> CandidateTest:
    """
    Submit/finish test for QR code candidates using UUID authentication.
    """
    # Verify UUID access
    candidate_test = verify_candidate_uuid_access(
        session, candidate_test_id, candidate_uuid
    )

    if candidate_test.is_submitted:
        raise HTTPException(status_code=400, detail="Test already submitted")

    # Mark test as submitted and set end time
    candidate_test.is_submitted = True
    candidate_test.end_time = get_timezone_aware_now()

    session.add(candidate_test)
    session.commit()
    session.refresh(candidate_test)
    return candidate_test


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

    state_query = select(State).join(TestState).where(TestState.test_id == test.id)
    states = session.exec(state_query).all()
    assigned_ids = candidate_test.question_revision_ids
    if not assigned_ids:
        raise HTTPException(status_code=404, detail="No questions assigned")
    question_revision_query = select(QuestionRevision).where(
        col(QuestionRevision.id).in_(assigned_ids)
    )
    question_revisions_map = {
        q.id: q for q in session.exec(question_revision_query).all()
    }
    ordered_questions = [
        question_revisions_map[qid]
        for qid in assigned_ids
        if qid in question_revisions_map
    ]
    if test.marks_level == "test":
        for q in ordered_questions:
            q.marking_scheme = test.marking_scheme

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
            marking_scheme=q.marking_scheme,
        )
        for q in ordered_questions
    ]

    return TestCandidatePublic(
        **test.model_dump(),
        question_revisions=candidate_questions,
        tags=tags,
        states=states,
        total_questions=len(candidate_questions),
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


@router.get(
    "/summary",
    response_model=TestStatusSummary,
    dependencies=[Depends(permission_dependency("read_candidate_test"))],
)
def get_test_summary(
    session: SessionDep,
    current_user: CurrentUser,
    start_date: datetime | None = Query(
        None, description="Start date in YYYY-MM-DD format"
    ),
    end_date: datetime | None = Query(
        None, description="End date in YYYY-MM-DD format"
    ),
) -> TestStatusSummary:
    query = (
        select(CandidateTest, Test)
        .join(Test)
        .where(CandidateTest.test_id == Test.id)
        .join(User)
        .where(Test.created_by_id == User.id)
        .where(User.organization_id == current_user.organization_id)
    )

    if start_date and Test.start_time is not None:
        query = query.where(Test.start_time >= start_date)

    if end_date and Test.end_time is not None:
        query = query.where(Test.end_time <= end_date)

    results = session.exec(query).all()
    submitted = 0
    not_submitted = 0
    not_submitted_active = 0
    not_submitted_inactive = 0
    now = get_current_time()
    for candidate_test, test in results:
        c_start = candidate_test.start_time
        c_end = candidate_test.end_time
        t_start = test.start_time
        t_end = test.end_time
        time_limit = getattr(test, "time_limit", None)
        if candidate_test.is_submitted or c_end:
            submitted += 1
            continue
        not_submitted += 1

        potential_time_spent = (now - c_start).total_seconds() / 60 if c_start else None

        if not t_start or not t_end:
            if (
                not time_limit
                or potential_time_spent is None
                or potential_time_spent < time_limit
            ):
                not_submitted_active += 1
            else:
                not_submitted_inactive += 1
        elif t_end and now < t_end:
            if time_limit:
                if potential_time_spent is None or potential_time_spent < time_limit:
                    not_submitted_active += 1
                else:
                    not_submitted_inactive += 1
            else:
                not_submitted_active += 1
        else:
            not_submitted_inactive += 1

    return TestStatusSummary(
        total_test_submitted=submitted,
        total_test_not_submitted=not_submitted,
        not_submitted_active=not_submitted_active,
        not_submitted_inactive=not_submitted_inactive,
    )


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


def convert_to_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    if isinstance(value, str):
        if value.startswith("{") and value.endswith("}"):
            return value[1:-1].split(",")
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
            return [v.strip() for v in value.split(",")]

        return [value.strip()]

    return [str(value)]


@router.get("/result/{candidate_test_id}", response_model=Result)
def get_test_result(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> Result:
    candidate_test = session.get(CandidateTest, candidate_test_id)

    if not candidate_test:
        raise HTTPException(status_code=404, detail="Candidate test not found")
    test = session.get(Test, candidate_test.test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found")
    if not test.show_result:
        raise HTTPException(
            status_code=403, detail="Results are not visible for this test"
        )

    verify_candidate_uuid_access(session, candidate_test_id, candidate_uuid)
    if test.random_questions and candidate_test.question_revision_ids:
        joined_data = session.exec(
            select(CandidateTestAnswer, QuestionRevision)
            .join(QuestionRevision)
            .where(
                CandidateTestAnswer.candidate_test_id == candidate_test_id,
                col(CandidateTestAnswer.question_revision_id).in_(
                    candidate_test.question_revision_ids
                ),
            )
        ).all()
    else:
        joined_data = session.exec(
            select(CandidateTestAnswer, QuestionRevision)
            .join(QuestionRevision)
            .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
        ).all()

    correct = 0
    incorrect = 0
    mandatory_not_attempted = 0
    optional_not_attempted = 0

    for answer, revision in joined_data:
        if not answer.response:
            if revision.is_mandatory:
                mandatory_not_attempted += 1
            else:
                optional_not_attempted += 1
        else:
            if revision.question_type.value in ["single-choice", "multi-choice"]:
                response_list = convert_to_list(answer.response)
                correct_list = convert_to_list(revision.correct_answer)

                if set(response_list) == set(correct_list):
                    correct += 1
                else:
                    incorrect += 1
    return Result(
        correct_answer=correct,
        incorrect_answer=incorrect,
        mandatory_not_attempted=mandatory_not_attempted,
        optional_not_attempted=optional_not_attempted,
    )


@router.get("/time_left/{candidate_test_id}", response_model=TimeLeft)
def get_time_left(
    candidate_test_id: int,
    session: SessionDep,
    candidate_uuid: uuid.UUID = Query(
        ..., description="Candidate UUID for verification"
    ),
) -> TimeLeft:
    verify_candidate_uuid_access(session, candidate_test_id, candidate_uuid)
    candidate_test = session.exec(
        select(CandidateTest).where(CandidateTest.id == candidate_test_id)
    ).first()
    if not candidate_test:
        raise HTTPException(status_code=404, detail="Candidate test not found")
    test = session.exec(select(Test).where(Test.id == candidate_test.test_id)).first()

    if not test:
        raise HTTPException(status_code=404, detail="Associated test not found")
    current_time = get_current_time()

    elapsed_time = current_time - candidate_test.start_time
    remaining_times = []
    if test.time_limit is not None:
        remaining_by_limit = timedelta(minutes=float(test.time_limit)) - elapsed_time
        remaining_times.append(remaining_by_limit)
    if test.end_time is not None:
        remaining_by_endtime = test.end_time - current_time
        remaining_times.append(remaining_by_endtime)
    if not remaining_times:
        return TimeLeft(time_left=None)
    final_time_left = min(remaining_times)
    if final_time_left.total_seconds() <= 0:
        return TimeLeft(time_left=0)

    time_left = int(final_time_left.total_seconds())
    return TimeLeft(time_left=time_left)
