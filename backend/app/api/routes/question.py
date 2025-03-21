from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException
from sqlmodel import and_, select

from app.api.deps import SessionDep
from app.models import (
    Block,
    District,
    Message,
    Question,
    QuestionCreate,
    QuestionLocation,
    QuestionLocationCreate,
    QuestionLocationPublic,
    QuestionPublic,
    QuestionRevision,
    QuestionRevisionCreate,
    QuestionUpdate,
    State,
)

router = APIRouter(prefix="/questions", tags=["Questions"])


def build_question_response(
    question: Question, revision: QuestionRevision, locations: list[QuestionLocation]
) -> QuestionPublic:
    """Build a standardized QuestionPublic response."""
    # Convert complex types to dictionaries for JSON serialization
    options_dict = None
    if revision.options:
        options_dict = [
            opt.dict() if hasattr(opt, "dict") else opt for opt in revision.options
        ]

    marking_scheme_dict = (
        revision.marking_scheme.dict()
        if revision.marking_scheme and hasattr(revision.marking_scheme, "dict")
        else revision.marking_scheme
    )

    media_dict = (
        revision.media.dict()
        if revision.media and hasattr(revision.media, "dict")
        else revision.media
    )

    return QuestionPublic(
        id=question.id,
        organization_id=question.organization_id,
        created_date=question.created_date,
        modified_date=question.modified_date,
        is_active=question.is_active,
        is_deleted=question.is_deleted,
        # Current revision data
        question_text=revision.question_text,
        instructions=revision.instructions,
        question_type=revision.question_type,
        options=options_dict,
        correct_answer=revision.correct_answer,
        subjective_answer_limit=revision.subjective_answer_limit,
        is_mandatory=revision.is_mandatory,
        marking_scheme=marking_scheme_dict,
        solution=revision.solution,
        media=media_dict,
        # Location data
        locations=[
            QuestionLocationPublic(
                id=loc.id,
                state_id=loc.state_id,
                district_id=loc.district_id,
                block_id=loc.block_id,
                state_name=loc.state.name if loc.state else None,
                district_name=loc.district.name if loc.district else None,
                block_name=loc.block.name if loc.block else None,
            )
            for loc in locations
        ]
        if locations
        else [],
    )


def prepare_for_db(data):
    """Helper function to prepare data for database by converting objects to dicts"""
    # Handle options
    if data.options:
        options = [
            opt.dict() if hasattr(opt, "dict") and callable(opt.dict) else opt
            for opt in data.options
        ]
    else:
        options = None

    # Handle marking scheme
    if (
        data.marking_scheme
        and hasattr(data.marking_scheme, "dict")
        and callable(data.marking_scheme.dict)
    ):
        marking_scheme = data.marking_scheme.dict()
    else:
        marking_scheme = data.marking_scheme

    # Handle media
    if data.media and hasattr(data.media, "dict") and callable(data.media.dict):
        media = data.media.dict()
    else:
        media = data.media

    return options, marking_scheme, media


@router.post("/", response_model=QuestionPublic)
def create_question(
    question_create: QuestionCreate, session: SessionDep
) -> QuestionPublic:
    """Create a new question with its initial revision and optional location."""
    # Create the main question record
    question = Question(
        organization_id=question_create.organization_id,
    )
    session.add(question)
    session.flush()

    # Prepare data for JSON serialization
    options, marking_scheme, media = prepare_for_db(question_create)

    # Create the revision with serialized data
    revision = QuestionRevision(
        question_id=question.id,
        question_text=question_create.question_text,
        instructions=question_create.instructions,
        question_type=question_create.question_type,
        options=options,  # Now serialized
        correct_answer=question_create.correct_answer,
        subjective_answer_limit=question_create.subjective_answer_limit,
        is_mandatory=question_create.is_mandatory,
        marking_scheme=marking_scheme,  # Now serialized
        solution=question_create.solution,
        media=media,  # Now serialized
    )
    session.add(revision)
    session.flush()

    question.last_revision_id = revision.id

    locations = []
    if any(
        [
            question_create.state_id,
            question_create.district_id,
            question_create.block_id,
        ]
    ):
        location = QuestionLocation(
            question_id=question.id,
            state_id=question_create.state_id,
            district_id=question_create.district_id,
            block_id=question_create.block_id,
        )
        session.add(location)
        locations.append(location)

    session.commit()
    session.refresh(question)

    return build_question_response(question, revision, locations)


@router.get("/", response_model=list[QuestionPublic])
def get_questions(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    organization_id: int = None,
    state_id: int = None,
    district_id: int = None,
    block_id: int = None,
    is_active: bool = None,
    is_deleted: bool = False,  # Default to showing non-deleted questions
) -> list[QuestionPublic]:
    """Get all questions with optional filtering."""
    # Start with a basic query
    query = select(Question)

    # Apply filters only if they're provided
    if is_deleted is not None:
        query = query.where(Question.is_deleted == is_deleted)

    if is_active is not None:
        query = query.where(Question.is_active == is_active)

    if organization_id is not None:
        query = query.where(Question.organization_id == organization_id)

    # Handle location-based filtering
    if any([state_id, district_id, block_id]):
        location_query = select(QuestionLocation.question_id)
        location_filters = []

        if state_id is not None:
            location_filters.append(QuestionLocation.state_id == state_id)
        if district_id is not None:
            location_filters.append(QuestionLocation.district_id == district_id)
        if block_id is not None:
            location_filters.append(QuestionLocation.block_id == block_id)

        if location_filters:
            location_query = location_query.where(and_(*location_filters))
            question_ids = session.exec(location_query).all()
            if question_ids:  # Only apply filter if we found matching locations
                query = query.where(Question.id.in_(question_ids))

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query and get all questions
    questions = session.exec(query).all()

    result = []
    for question in questions:
        # Skip questions without a valid last_revision_id
        if not question.last_revision_id:
            continue

        latest_revision = session.get(QuestionRevision, question.last_revision_id)
        if not latest_revision:
            continue

        locations_query = select(QuestionLocation).where(
            QuestionLocation.question_id == question.id
        )
        locations = session.exec(locations_query).all()

        question_data = build_question_response(question, latest_revision, locations)
        result.append(question_data)

    return result


@router.get("/{question_id}", response_model=QuestionPublic)
def get_question_by_id(question_id: int, session: SessionDep) -> QuestionPublic:
    """Get a question by its ID."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    latest_revision = session.get(QuestionRevision, question.last_revision_id)
    if not latest_revision:
        raise HTTPException(status_code=404, detail="Question revision not found")

    locations_query = select(QuestionLocation).where(
        QuestionLocation.question_id == question.id
    )
    locations = session.exec(locations_query).all()

    return build_question_response(question, latest_revision, locations)


@router.put("/{question_id}", response_model=QuestionPublic)
def update_question(
    question_id: int,
    updated_data: QuestionUpdate = Body(...),  # is_active, is_deleted
    session: SessionDep = None,
) -> QuestionPublic:
    """Update question metadata (not content - use revisions for that)."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Update basic question attributes
    question_data = updated_data.model_dump(exclude_unset=True)
    for key, value in question_data.items():
        setattr(question, key, value)

    question.modified_date = datetime.now(timezone.utc)
    session.add(question)
    session.commit()
    session.refresh(question)

    latest_revision = session.get(QuestionRevision, question.last_revision_id)

    locations_query = select(QuestionLocation).where(
        QuestionLocation.question_id == question.id
    )
    locations = session.exec(locations_query).all()

    return build_question_response(question, latest_revision, locations)


@router.post("/{question_id}/revisions", response_model=QuestionPublic)
def create_question_revision(
    question_id: int,
    revision_data: QuestionRevisionCreate,
    session: SessionDep,
) -> QuestionPublic:
    """Create a new revision for an existing question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Prepare data for JSON serialization
    options, marking_scheme, media = prepare_for_db(revision_data)

    new_revision = QuestionRevision(
        question_id=question_id,
        question_text=revision_data.question_text,
        instructions=revision_data.instructions,
        question_type=revision_data.question_type,
        options=options,  # Now serialized
        correct_answer=revision_data.correct_answer,
        subjective_answer_limit=revision_data.subjective_answer_limit,
        is_mandatory=revision_data.is_mandatory,
        marking_scheme=marking_scheme,  # Now serialized
        solution=revision_data.solution,
        media=media,  # Now serialized
    )
    session.add(new_revision)
    session.flush()

    question.last_revision_id = new_revision.id
    question.modified_date = datetime.now(timezone.utc)
    session.add(question)
    session.commit()
    session.refresh(question)
    session.refresh(new_revision)

    locations_query = select(QuestionLocation).where(
        QuestionLocation.question_id == question.id
    )
    locations = session.exec(locations_query).all()

    return build_question_response(question, new_revision, locations)


@router.get("/{question_id}/revisions", response_model=list[dict])
def get_question_revisions(question_id: int, session: SessionDep) -> list[dict]:
    """Get all revisions for a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    revisions_query = (
        select(QuestionRevision)
        .where(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.created_date.desc())
    )
    revisions = session.exec(revisions_query).all()

    return [
        {
            "id": rev.id,
            "created_date": rev.created_date,
            "text": rev.question_text,
            "type": rev.question_type,
            "is_current": rev.id == question.last_revision_id,
        }
        for rev in revisions
    ]


@router.get("/revisions/{revision_id}", response_model=dict)
def get_revision(revision_id: int, session: SessionDep) -> dict:
    """Get a specific question revision by its ID."""
    revision = session.get(QuestionRevision, revision_id)
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    # Check if parent question exists and is not deleted
    question = session.get(Question, revision.question_id)
    if not question or question.is_deleted:
        raise HTTPException(
            status_code=404, detail="Parent question not found or deleted"
        )

    # Convert complex objects to dicts for serialization
    options_dict = None
    if revision.options:
        options_dict = [
            opt.dict() if hasattr(opt, "dict") else opt for opt in revision.options
        ]

    marking_scheme_dict = (
        revision.marking_scheme.dict()
        if revision.marking_scheme and hasattr(revision.marking_scheme, "dict")
        else revision.marking_scheme
    )

    media_dict = (
        revision.media.dict()
        if revision.media and hasattr(revision.media, "dict")
        else revision.media
    )

    # Return as dict instead of model to add dynamic is_current attribute
    return {
        "id": revision.id,
        "question_id": revision.question_id,
        "created_date": revision.created_date,
        "modified_date": revision.modified_date,
        "is_active": revision.is_active,
        "is_deleted": revision.is_deleted,
        "question_text": revision.question_text,
        "instructions": revision.instructions,
        "question_type": revision.question_type,
        "options": options_dict,
        "correct_answer": revision.correct_answer,
        "subjective_answer_limit": revision.subjective_answer_limit,
        "is_mandatory": revision.is_mandatory,
        "marking_scheme": marking_scheme_dict,
        "solution": revision.solution,
        "media": media_dict,
        "is_current": revision.id == question.last_revision_id,
    }


@router.post("/{question_id}/locations", response_model=QuestionLocationPublic)
def add_question_location(
    question_id: int,
    location_data: QuestionLocationCreate,
    session: SessionDep,
) -> QuestionLocationPublic:
    """Add a new location to a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    location = QuestionLocation(
        question_id=question_id,
        state_id=location_data.state_id,
        district_id=location_data.district_id,
        block_id=location_data.block_id,
    )
    session.add(location)
    session.commit()
    session.refresh(location)

    # Get related location names for response
    state_name = None
    district_name = None
    block_name = None

    if location.state_id:
        state = session.get(State, location.state_id)
        if state:
            state_name = state.name

    if location.district_id:
        district = session.get(District, location.district_id)
        if district:
            district_name = district.name

    if location.block_id:
        block = session.get(Block, location.block_id)
        if block:
            block_name = block.name

    return QuestionLocationPublic(
        id=location.id,
        state_id=location.state_id,
        district_id=location.district_id,
        block_id=location.block_id,
        state_name=state_name,
        district_name=district_name,
        block_name=block_name,
    )


@router.delete("/{question_id}")
def delete_question(question_id: int, session: SessionDep) -> Message:
    """Soft delete a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Soft delete
    question.is_deleted = True
    question.is_active = False
    question.modified_date = datetime.now(timezone.utc)
    session.add(question)
    session.commit()

    return Message(message="Question deleted successfully")


@router.get("/{question_id}/tests", response_model=list[dict])
def get_question_tests(question_id: int, session: SessionDep) -> list[dict]:
    """Get all tests that include this question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    return [
        {"id": test.id, "name": test.name, "created_date": test.created_date}
        for test in question.tests
    ]


@router.get("/{question_id}/candidate-tests", response_model=list[dict])
def get_question_candidate_tests(question_id: int, session: SessionDep) -> list[dict]:
    """Get all candidate tests that include this question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    return [
        {
            "id": ct.id,
            "candidate_id": ct.candidate_id,
            "test_id": ct.test_id,
            "start_time": ct.start_time,
            "is_submitted": ct.is_submitted,
        }
        for ct in question.candidate_test
    ]
