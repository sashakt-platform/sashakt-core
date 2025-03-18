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
        options=revision.options,
        correct_answer=revision.correct_answer,
        subjective_answer_limit=revision.subjective_answer_limit,
        is_mandatory=revision.is_mandatory,
        marking_scheme=revision.marking_scheme,
        solution=revision.solution,
        media=revision.media,
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


@router.post("/", response_model=QuestionPublic)
def create_question(
    question_create: QuestionCreate, session: SessionDep
) -> QuestionPublic:
    """Create a new question with its initial revision and optional location."""
    question = Question(
        organization_id=question_create.organization_id,
    )
    session.add(question)
    session.flush()

    revision = QuestionRevision(
        question_id=question.id,
        question_text=question_create.question_text,
        instructions=question_create.instructions,
        question_type=question_create.question_type,
        options=question_create.options,
        correct_answer=question_create.correct_answer,
        subjective_answer_limit=question_create.subjective_answer_limit,
        is_mandatory=question_create.is_mandatory,
        marking_scheme=question_create.marking_scheme,
        solution=question_create.solution,
        media=question_create.media,
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
) -> list[QuestionPublic]:
    """Get all questions with optional filtering."""
    query = select(Question).where(not Question.is_deleted)

    if organization_id is not None:
        query = query.where(Question.organization_id == organization_id)

    if is_active is not None:
        query = query.where(Question.is_active == is_active)

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
            query = query.where(Question.id.in_(question_ids))

    # Apply pagination
    query = query.offset(skip).limit(limit)
    questions = session.exec(query).all()

    result = []
    for question in questions:
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

    new_revision = QuestionRevision(
        question_id=question_id,
        question_text=revision_data.question_text,
        instructions=revision_data.instructions,
        question_type=revision_data.question_type,
        options=revision_data.options,
        correct_answer=revision_data.correct_answer,
        subjective_answer_limit=revision_data.subjective_answer_limit,
        is_mandatory=revision_data.is_mandatory,
        marking_scheme=revision_data.marking_scheme,
        solution=revision_data.solution,
        media=revision_data.media,
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


@router.get("/revisions/{revision_id}", response_model=QuestionRevision)
def get_revision(revision_id: int, session: SessionDep) -> QuestionRevision:
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

    # Add is_current as a dynamic attribute
    revision.is_current = revision.id == question.last_revision_id
    return revision


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
