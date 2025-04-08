from datetime import datetime, timezone
from typing import Any, TypedDict

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
    QuestionTag,
    QuestionTagCreate,
    QuestionUpdate,
    State,
    Tag,
    TagPublic,
)

router = APIRouter(prefix="/questions", tags=["Questions"])


def build_question_response(
    question: Question,
    revision: QuestionRevision,
    locations: list[QuestionLocation],
    tags: list[Tag] | None = None,
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

    # Prepare tag information
    tag_list = []
    if tags:
        tag_list = [
            TagPublic(
                id=tag.id,
                name=tag.name,
                tag_type_id=tag.tag_type_id,
                description=tag.description,
                created_by_id=tag.created_by_id,
                organization_id=tag.organization_id,
                created_date=tag.created_date,
                modified_date=tag.modified_date,
                is_active=tag.is_active,
                is_deleted=tag.is_deleted,
            )
            for tag in tags
        ]

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
        created_by_id=revision.created_by_id,
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
        tags=tag_list,
    )


def prepare_for_db(
    data: QuestionCreate | QuestionRevisionCreate,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Helper function to prepare data for database by converting objects to dicts"""
    # Handle options
    options: list[dict[str, Any]] | None = None
    if data.options:
        options = [
            opt.dict() if hasattr(opt, "dict") and callable(opt.dict) else opt
            for opt in data.options
        ]

    # Handle marking scheme
    marking_scheme: dict[str, Any] | None = None
    if (
        data.marking_scheme
        and hasattr(data.marking_scheme, "dict")
        and callable(data.marking_scheme.dict)
    ):
        marking_scheme = data.marking_scheme.dict()
    else:
        marking_scheme = data.marking_scheme

    # Handle media
    media: dict[str, Any] | None = None
    if data.media and hasattr(data.media, "dict") and callable(data.media.dict):
        media = data.media.dict()
    else:
        media = data.media

    return options, marking_scheme, media


@router.post("/", response_model=QuestionPublic)
def create_question(
    question_create: QuestionCreate, session: SessionDep
) -> QuestionPublic:
    """Create a new question with its initial revision, optional location, and tags."""
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
        created_by_id=question_create.created_by_id,
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

    locations: list[QuestionLocation] = []
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

    tags: list[Tag] = []
    if question_create.tag_ids:
        for tag_id in question_create.tag_ids:
            tag = session.get(Tag, tag_id)
            if tag:
                question_tag = QuestionTag(
                    question_id=question.id,
                    tag_id=tag_id,
                )
                session.add(question_tag)
                tags.append(tag)

    session.commit()
    session.refresh(question)

    return build_question_response(question, revision, locations, tags)


# TypedDict classes with all required fields
class QuestionRevisionInfo(TypedDict):
    id: int
    created_date: datetime
    text: str
    type: str
    is_current: bool
    created_by_id: int


class RevisionDetailDict(TypedDict):
    id: int
    question_id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool | None
    question_text: str
    instructions: str | None
    question_type: str
    options: list[dict[str, Any]] | None
    correct_answer: Any
    subjective_answer_limit: int | None
    is_mandatory: bool
    marking_scheme: dict[str, Any] | None
    solution: str | None
    media: dict[str, Any] | None
    is_current: bool
    created_by_id: int


class QuestionTagResponse(TypedDict):
    id: int
    question_id: int
    tag_id: int
    tag_name: str
    created_date: datetime


class TestInfoDict(TypedDict):
    id: int
    name: str
    created_date: datetime


class CandidateTestInfoDict(TypedDict):
    id: int
    candidate_id: int
    test_id: int
    start_time: datetime
    is_submitted: bool


@router.get("/", response_model=list[QuestionPublic])
def get_questions(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    organization_id: int | None = None,
    state_id: int | None = None,
    district_id: int | None = None,
    block_id: int | None = None,
    tag_id: int | None = None,
    created_by_id: int | None = None,
    is_active: bool | None = None,
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

    # Handle tag-based filtering
    if tag_id is not None:
        tag_query = select(QuestionTag.question_id).where(QuestionTag.tag_id == tag_id)
        question_ids_with_tag = session.exec(tag_query).all()
        if question_ids_with_tag:  # Only apply filter if we found matching tags
            query = query.where(Question.id.in_(question_ids_with_tag))
        else:
            # If no questions have this tag, return empty list
            return []

    # Handle creator-based filtering
    if created_by_id is not None:
        questions_by_creator: list[int] = []
        all_questions = session.exec(query).all()

        for q in all_questions:
            if q.last_revision_id is not None:
                revision = session.get(QuestionRevision, q.last_revision_id)
                if revision is not None and revision.created_by_id == created_by_id:
                    questions_by_creator.append(q.id)

        if questions_by_creator:
            query = select(Question).where(Question.id.in_(questions_by_creator))
        else:
            return []

    # Handle location-based filtering
    if any([state_id is not None, district_id is not None, block_id is not None]):
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
            else:
                return []

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query and get all questions
    questions = session.exec(query).all()

    result: list[QuestionPublic] = []
    for question in questions:
        # Skip questions without a valid last_revision_id
        if question.last_revision_id is None:
            continue

        latest_revision = session.get(QuestionRevision, question.last_revision_id)
        if latest_revision is None:
            continue

        locations_query = select(QuestionLocation).where(
            QuestionLocation.question_id == question.id
        )
        locations = session.exec(locations_query).all()

        tags_query = (
            select(Tag).join(QuestionTag).where(QuestionTag.question_id == question.id)
        )
        tags = session.exec(tags_query).all()

        question_data = build_question_response(
            question, latest_revision, list(locations), list(tags)
        )
        result.append(question_data)

    return result


@router.get("/{question_id}", response_model=QuestionPublic)
def get_question_by_id(question_id: int, session: SessionDep) -> QuestionPublic:
    """Get a question by its ID."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    latest_revision = session.get(QuestionRevision, question.last_revision_id)
    if latest_revision is None:
        raise HTTPException(status_code=404, detail="Question revision not found")

    locations_query = select(QuestionLocation).where(
        QuestionLocation.question_id == question.id
    )
    locations = session.exec(locations_query).all()

    tags_query = (
        select(Tag).join(QuestionTag).where(QuestionTag.question_id == question.id)
    )
    tags = session.exec(tags_query).all()

    return build_question_response(
        question, latest_revision, list(locations), list(tags)
    )


@router.put("/{question_id}", response_model=QuestionPublic)
def update_question(
    question_id: int,
    updated_data: QuestionUpdate = Body(...),  # is_active, is_deleted
    session: SessionDep = Body(...),
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
    if latest_revision is None:
        raise HTTPException(status_code=404, detail="Question revision not found")

    locations_query = select(QuestionLocation).where(
        QuestionLocation.question_id == question.id
    )
    locations = session.exec(locations_query).all()

    tags_query = (
        select(Tag).join(QuestionTag).where(QuestionTag.question_id == question.id)
    )
    tags = session.exec(tags_query).all()

    return build_question_response(
        question, latest_revision, list(locations), list(tags)
    )


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
        created_by_id=revision_data.created_by_id,
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

    tags_query = (
        select(Tag).join(QuestionTag).where(QuestionTag.question_id == question.id)
    )
    tags = session.exec(tags_query).all()

    return build_question_response(question, new_revision, list(locations), list(tags))


@router.get("/{question_id}/revisions", response_model=list[QuestionRevisionInfo])
def get_question_revisions(
    question_id: int, session: SessionDep
) -> list[QuestionRevisionInfo]:
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

    result: list[QuestionRevisionInfo] = []
    for rev in revisions:
        # Ensure all fields have non-None values before creating TypedDict
        if rev.id is not None and rev.created_date is not None:
            result.append(
                QuestionRevisionInfo(
                    id=rev.id,
                    created_date=rev.created_date,
                    text=rev.question_text,
                    type=rev.question_type,
                    is_current=(rev.id == question.last_revision_id),
                    created_by_id=rev.created_by_id,
                )
            )

    return result


@router.get("/revisions/{revision_id}", response_model=RevisionDetailDict)
def get_revision(revision_id: int, session: SessionDep) -> RevisionDetailDict:
    """Get a specific question revision by its ID."""
    revision = session.get(QuestionRevision, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    # Ensure we have non-None values for required fields
    if (
        revision.id is None
        or revision.question_id is None
        or revision.created_date is None
        or revision.modified_date is None
    ):
        raise HTTPException(
            status_code=500, detail="Revision has missing required fields"
        )

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
    return RevisionDetailDict(
        id=revision.id,
        question_id=revision.question_id,
        created_date=revision.created_date,
        modified_date=revision.modified_date,
        is_active=revision.is_active,
        is_deleted=revision.is_deleted,
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
        is_current=(revision.id == question.last_revision_id),
        created_by_id=revision.created_by_id,
    )


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

    # Ensure we have a valid ID after refresh
    if location.id is None:
        raise HTTPException(status_code=500, detail="Failed to create location")

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


@router.post("/{question_id}/tags", response_model=QuestionTagResponse)
def add_question_tag(
    question_id: int,
    tag_data: QuestionTagCreate,
    session: SessionDep,
) -> QuestionTagResponse:
    """Add a new tag to a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check if tag exists
    tag = session.get(Tag, tag_data.tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Check if relationship already exists
    existing_query = select(QuestionTag).where(
        QuestionTag.question_id == question_id, QuestionTag.tag_id == tag_data.tag_id
    )
    existing = session.exec(existing_query).first()
    if existing and existing.id is not None and existing.created_date is not None:
        return QuestionTagResponse(
            id=existing.id,
            question_id=existing.question_id,
            tag_id=existing.tag_id,
            tag_name=tag.name,
            created_date=existing.created_date,
        )

    # Create new relationship
    question_tag = QuestionTag(
        question_id=question_id,
        tag_id=tag_data.tag_id,
    )
    session.add(question_tag)
    session.commit()
    session.refresh(question_tag)

    # Ensure we have valid ID and created_date after refresh
    if question_tag.id is None or question_tag.created_date is None:
        raise HTTPException(status_code=500, detail="Failed to create tag relationship")

    return QuestionTagResponse(
        id=question_tag.id,
        question_id=question_tag.question_id,
        tag_id=question_tag.tag_id,
        tag_name=tag.name,
        created_date=question_tag.created_date,
    )


@router.delete("/{question_id}/tags/{tag_id}", response_model=Message)
def remove_question_tag(
    question_id: int,
    tag_id: int,
    session: SessionDep,
) -> Message:
    """Remove a tag from a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Find the relationship
    tag_query = select(QuestionTag).where(
        QuestionTag.question_id == question_id, QuestionTag.tag_id == tag_id
    )
    question_tag = session.exec(tag_query).first()
    if not question_tag:
        raise HTTPException(status_code=404, detail="Tag not assigned to this question")

    # Delete the relationship
    session.delete(question_tag)
    session.commit()

    return Message(message="Tag removed from question successfully")


@router.get("/{question_id}/tags", response_model=list[TagPublic])
def get_question_tags(
    question_id: int,
    session: SessionDep,
) -> list[TagPublic]:
    """Get all tags for a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Get tags for this question
    tags_query = (
        select(Tag).join(QuestionTag).where(QuestionTag.question_id == question.id)
    )
    tags = session.exec(tags_query).all()

    return [
        TagPublic(
            id=tag.id,
            name=tag.name,
            description=tag.description,
            tag_type_id=tag.tag_type_id,
            created_by_id=tag.created_by_id,
            organization_id=tag.organization_id,
            created_date=tag.created_date,
            modified_date=tag.modified_date,
            is_active=tag.is_active,
            is_deleted=tag.is_deleted,
        )
        for tag in tags
    ]


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


@router.get("/{question_id}/tests", response_model=list[TestInfoDict])
def get_question_tests(question_id: int, session: SessionDep) -> list[TestInfoDict]:
    """Get all tests that include this question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    result: list[TestInfoDict] = []
    for test in question.tests:
        # Ensure all required fields are non-None
        if test.id is not None and test.created_date is not None:
            result.append(
                TestInfoDict(id=test.id, name=test.name, created_date=test.created_date)
            )

    return result


@router.get(
    "/{question_id}/candidate-tests", response_model=list[CandidateTestInfoDict]
)
def get_question_candidate_tests(
    question_id: int, session: SessionDep
) -> list[CandidateTestInfoDict]:
    """Get all candidate tests that include this question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    result: list[CandidateTestInfoDict] = []
    for ct in question.candidate_test:
        # Ensure all required fields are non-None
        if ct.id is not None and ct.start_time is not None:
            result.append(
                CandidateTestInfoDict(
                    id=ct.id,
                    candidate_id=ct.candidate_id,
                    test_id=ct.test_id,
                    start_time=ct.start_time,
                    is_submitted=ct.is_submitted,
                )
            )

    return result
