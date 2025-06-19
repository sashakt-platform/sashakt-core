import csv
from datetime import datetime
from io import StringIO
from typing import Any

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import desc
from sqlmodel import or_, select
from typing_extensions import TypedDict

from app.api.deps import SessionDep
from app.models import (
    Block,
    CandidateTest,
    District,
    Message,
    Organization,
    Question,
    QuestionCreate,
    QuestionLocation,
    QuestionLocationPublic,
    QuestionLocationsCreate,
    QuestionPublic,
    QuestionRevision,
    QuestionRevisionCreate,
    QuestionTag,
    QuestionTagsCreate,
    QuestionUpdate,
    State,
    Tag,
    TagPublic,
    TagType,
    Test,
    User,
)
from app.models.question import Option

router = APIRouter(prefix="/questions", tags=["Questions"])


def get_tag_type_by_id(session: SessionDep, tag_type_id: int) -> TagType | None:
    """Helper function to get TagType by ID."""
    tag_type = session.get(TagType, tag_type_id)
    if not tag_type or tag_type.is_deleted:
        return None
    return tag_type


def build_question_response(
    session: SessionDep,
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
            opt
            if isinstance(opt, dict)
            else opt.dict()
            if hasattr(opt, "dict") and callable(opt.dict)
            else vars(opt)
            if hasattr(opt, "__dict__")
            else opt
            for opt in revision.options
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
    tag_list: list[TagPublic] = []
    if tags:
        tag_list = [
            TagPublic(
                id=tag.id,
                name=tag.name,
                tag_type=tag_type,
                description=tag.description,
                created_by_id=tag.created_by_id,
                organization_id=tag.organization_id,
                created_date=tag.created_date,
                modified_date=tag.modified_date,
                is_active=tag.is_active,
                is_deleted=tag.is_deleted,
            )
            for tag in tags
            if (tag_type := get_tag_type_by_id(session, tag_type_id=tag.tag_type_id))
        ]

    # Prepare location information
    location_list = []
    if locations:
        location_list = [
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
        latest_question_revision_id=revision.id,
        created_by_id=revision.created_by_id,
        # Location data
        locations=location_list,
        tags=tag_list,
    )


def prepare_for_db(
    data: QuestionCreate | QuestionRevisionCreate,
) -> tuple[list[Option] | None, dict[str, float] | None, dict[str, Any] | None]:
    """Helper function to prepare data for database by converting objects to dicts"""
    # Handle options
    options: list[Option] | None = None
    if data.options:
        options = [
            opt
            if isinstance(opt, dict)
            else opt.dict()
            if hasattr(opt, "dict") and callable(opt.dict)
            else vars(opt)
            if hasattr(opt, "__dict__")
            else opt
            for opt in data.options
        ]

    marking_scheme: dict[str, float] | None = None
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

    revision = QuestionRevision(
        question_id=question.id,
        created_by_id=question_create.created_by_id,
        question_text=question_create.question_text,
        instructions=question_create.instructions,
        question_type=question_create.question_type,
        options=options,
        correct_answer=question_create.correct_answer,
        subjective_answer_limit=question_create.subjective_answer_limit,
        is_mandatory=question_create.is_mandatory,
        marking_scheme=marking_scheme,
        solution=question_create.solution,
        media=media,
    )
    session.add(revision)
    session.flush()

    question.last_revision_id = revision.id

    # Create separate location rows for state, district, block
    # This allows each association to be uniquely identified and deleted if needed
    locations: list[QuestionLocation] = []

    # Handle state associations
    if question_create.state_ids:
        for state_id in question_create.state_ids:
            state_location = QuestionLocation(
                question_id=question.id,
                state_id=state_id,
                district_id=None,
                block_id=None,
            )
            session.add(state_location)
            locations.append(state_location)

    # Handle district associations
    if question_create.district_ids:
        for district_id in question_create.district_ids:
            district_location = QuestionLocation(
                question_id=question.id,
                state_id=None,
                district_id=district_id,
                block_id=None,
            )
            session.add(district_location)
            locations.append(district_location)

    # Handle block associations
    if question_create.block_ids:
        for block_id in question_create.block_ids:
            block_location = QuestionLocation(
                question_id=question.id,
                state_id=None,
                district_id=None,
                block_id=block_id,
            )
            session.add(block_location)
            locations.append(block_location)

    # Add tags as separate entries, similar to the approach with locations
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
    # No need to set modified_date manually, as SQLModel will handle it via onupdate

    return build_question_response(session, question, revision, locations, tags)


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
    options: list[Option] | None
    correct_answer: Any
    subjective_answer_limit: int | None
    is_mandatory: bool
    marking_scheme: dict[str, float] | None  # Updated type to float
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
    state_ids: list[int] = Query(None),  # Support multiple states
    district_ids: list[int] = Query(None),  # Support multiple districts
    block_ids: list[int] = Query(None),  # Support multiple blocks
    tag_ids: list[int] = Query(None),  # Support multiple tags
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

    # Handle tag-based filtering with multiple tags
    if tag_ids:
        tag_query = select(QuestionTag.question_id).where(
            QuestionTag.tag_id.in_(tag_ids)  # type: ignore
        )
        question_ids_with_tags = session.exec(tag_query).all()
        if question_ids_with_tags:  # Only apply filter if we found matching tags
            query = query.where(Question.id.in_(question_ids_with_tags))  # type: ignore
        else:
            # If no questions have these tags, return empty list
            return []

    # Handle creator-based filtering
    if created_by_id is not None:
        questions_by_creator: list[int] = []
        all_questions = session.exec(query).all()

        for q in all_questions:
            if q.last_revision_id is not None:
                revision = session.get(QuestionRevision, q.last_revision_id)
                if revision is not None and revision.created_by_id == created_by_id:
                    if q.id is not None:
                        questions_by_creator.append(q.id)

        if questions_by_creator:
            query = select(Question).where(Question.id.in_(questions_by_creator))  # type: ignore
        else:
            return []

    # Handle location-based filtering with multiple locations
    if any([state_ids, district_ids, block_ids]):
        location_query = select(QuestionLocation.question_id)
        location_filters = []

        if state_ids:
            location_filters.append(QuestionLocation.state_id.in_(state_ids))  # type: ignore
        if district_ids:
            location_filters.append(QuestionLocation.district_id.in_(district_ids))  # type: ignore
        if block_ids:
            location_filters.append(QuestionLocation.block_id.in_(block_ids))  # type: ignore

        if location_filters:
            # Use OR between different location types (any match is valid)
            location_query = location_query.where(or_(*location_filters))
            question_ids = session.exec(location_query).all()
            if question_ids:  # Only apply filter if we found matching locations
                query = query.where(Question.id.in_(question_ids))  # type: ignore
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
            raise HTTPException(status_code=404, detail="Question revision not found")
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
            session, question, latest_revision, list(locations), list(tags)
        )
        result.append(question_data)

    return result


@router.get("/{question_id}/tests", response_model=list[TestInfoDict])
def get_question_tests(question_id: int, session: SessionDep) -> list[TestInfoDict]:
    """Get all tests that include this question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    test_info_dict_list: list[TestInfoDict] = []
    # Get all revisions for this question
    revisions_query = select(QuestionRevision).where(
        QuestionRevision.question_id == question_id
    )
    revisions = session.exec(revisions_query).all()

    # Collect unique test_ids
    test_ids = set()
    for revision in revisions:
        for test_question in revision.test_questions:
            test_ids.add(test_question.test_id)

    for test_id in test_ids:
        test = session.get(Test, test_id)
        if test and test.id is not None and test.created_date is not None:
            test_info = TestInfoDict(
                id=test.id, name=test.name, created_date=test.created_date
            )
            # Only add unique tests
            if not any(t["id"] == test_info["id"] for t in test_info_dict_list):
                test_info_dict_list.append(test_info)

    return test_info_dict_list


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

    candidate_test_info_list: list[CandidateTestInfoDict] = []

    # Get all revisions for this question
    revisions_query = select(QuestionRevision).where(
        QuestionRevision.question_id == question_id
    )
    revisions = session.exec(revisions_query).all()

    # Collect candidate_test_ids from all answers
    candidate_test_ids = set()
    for revision in revisions:
        for answer in revision.candidate_test_answers:
            candidate_test_ids.add(answer.candidate_test_id)

    # Query each CandidateTest directly
    for candidate_test_id in candidate_test_ids:
        candidate_test = session.get(CandidateTest, candidate_test_id)
        if (
            candidate_test
            and candidate_test.id is not None
            and candidate_test.start_time is not None
        ):
            candidate_test_info = CandidateTestInfoDict(
                id=candidate_test.id,
                candidate_id=candidate_test.candidate_id,
                test_id=candidate_test.test_id,
                start_time=candidate_test.start_time,
                is_submitted=candidate_test.is_submitted,
            )
            # Avoid duplicates
            if not any(
                ct["id"] == candidate_test_info["id"] for ct in candidate_test_info_list
            ):
                candidate_test_info_list.append(candidate_test_info)

    return candidate_test_info_list


@router.delete("/{question_id}")
def delete_question(question_id: int, session: SessionDep) -> Message:
    """Soft delete a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Soft delete
    question.is_deleted = True
    question.is_active = False
    # No need to set modified_date manually as it will be updated by SQLModel
    session.add(question)
    session.commit()

    return Message(message="Question deleted successfully")


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
        session, question, latest_revision, list(locations), list(tags)
    )


@router.put("/{question_id}", response_model=QuestionPublic)
def update_question(
    question_id: int,
    session: SessionDep,
    updated_data: QuestionUpdate = Body(...),  # is_active, is_deleted
) -> QuestionPublic:
    """Update question metadata (not content - use revisions for that)."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Update basic question attributes
    question_data = updated_data.model_dump(exclude_unset=True)
    for key, value in question_data.items():
        setattr(question, key, value)

    # No need to set modified_date manually, as it will be updated by SQLModel
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
        session, question, latest_revision, list(locations), list(tags)
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
    # No need to set modified_date manually
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

    return build_question_response(
        session, question, new_revision, list(locations), list(tags)
    )


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
        .order_by(desc(QuestionRevision.created_date))  # type: ignore
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
            opt
            if isinstance(opt, dict)
            else opt.dict()
            if hasattr(opt, "dict") and callable(opt.dict)
            else vars(opt)
            if hasattr(opt, "__dict__")
            else opt
            for opt in revision.options
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


@router.post("/{question_id}/locations", response_model=list[QuestionLocationPublic])
def add_question_locations(
    question_id: int,
    location_data: QuestionLocationsCreate,
    session: SessionDep,
) -> list[QuestionLocationPublic]:
    """Add one or more locations to a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    locations_to_add = location_data.locations
    if not locations_to_add:
        raise HTTPException(status_code=400, detail="No location data provided")

    results = []
    for loc_data in locations_to_add:
        # Determine which location type is being added
        location = None

        if loc_data.state_id:
            # Check if this state is already associated
            existing_query = select(QuestionLocation).where(
                QuestionLocation.question_id == question_id,
                QuestionLocation.state_id == loc_data.state_id,
            )
            if session.exec(existing_query).first():
                continue  # Skip already associated states

            location = QuestionLocation(
                question_id=question_id,
                state_id=loc_data.state_id,
                district_id=None,
                block_id=None,
            )
        elif loc_data.district_id:
            # Check if this district is already associated
            existing_query = select(QuestionLocation).where(
                QuestionLocation.question_id == question_id,
                QuestionLocation.district_id == loc_data.district_id,
            )
            if session.exec(existing_query).first():
                continue  # Skip already associated districts

            location = QuestionLocation(
                question_id=question_id,
                state_id=None,
                district_id=loc_data.district_id,
                block_id=None,
            )
        elif loc_data.block_id:
            # Check if this block is already associated
            existing_query = select(QuestionLocation).where(
                QuestionLocation.question_id == question_id,
                QuestionLocation.block_id == loc_data.block_id,
            )
            if session.exec(existing_query).first():
                continue  # Skip already associated blocks

            location = QuestionLocation(
                question_id=question_id,
                state_id=None,
                district_id=None,
                block_id=loc_data.block_id,
            )
        else:
            continue  # Skip invalid location data

        if location:
            session.add(location)
            session.flush()  # Flush to get the ID before processing names

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

            if location.id is not None:
                results.append(
                    QuestionLocationPublic(
                        id=location.id,
                        state_id=location.state_id,
                        district_id=location.district_id,
                        block_id=location.block_id,
                        state_name=state_name,
                        district_name=district_name,
                        block_name=block_name,
                    )
                )

    session.commit()
    return results


@router.delete("/{question_id}/locations/{location_id}", response_model=Message)
def remove_question_location(
    question_id: int,
    location_id: int,
    session: SessionDep,
) -> Message:
    """Remove a location from a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Find the location
    location = session.get(QuestionLocation, location_id)
    if not location or location.question_id != question_id:
        raise HTTPException(
            status_code=404, detail="Location not found for this question"
        )

    # Delete the location
    session.delete(location)
    session.commit()

    return Message(message="Location removed from question successfully")


@router.delete("/{question_id}/locations", response_model=Message)
def remove_question_locations(
    question_id: int,
    session: SessionDep,
    location_ids: list[int] = Query(..., description="Location IDs to remove"),
) -> Message:
    """Remove multiple locations from a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    if not location_ids:
        raise HTTPException(status_code=400, detail="No location IDs provided")

    deleted_count = 0
    for location_id in location_ids:
        # Find the location
        location = session.get(QuestionLocation, location_id)
        if location and location.question_id == question_id:
            session.delete(location)
            deleted_count += 1

    session.commit()
    return Message(
        message=f"Removed {deleted_count} location(s) from question successfully"
    )


@router.get("/{question_id}/tags", response_model=list[TagPublic])
def get_question_tags(question_id: int, session: SessionDep) -> list[TagPublic]:
    """Get all tags associated with a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Query all tags associated with this question
    tags_query = (
        select(Tag).join(QuestionTag).where(QuestionTag.question_id == question_id)
    )
    tags = session.exec(tags_query).all()

    # Convert to TagPublic model
    result = [
        TagPublic(
            id=tag.id,
            name=tag.name,
            tag_type=tag_type,
            description=tag.description,
            created_by_id=tag.created_by_id,
            organization_id=tag.organization_id,
            created_date=tag.created_date,
            modified_date=tag.modified_date,
            is_active=tag.is_active,
            is_deleted=tag.is_deleted,
        )
        for tag in tags
        if (tag_type := get_tag_type_by_id(session, tag_type_id=tag.tag_type_id))
    ]

    return result


@router.post("/{question_id}/tags", response_model=list[QuestionTagResponse])
def add_question_tags(
    question_id: int,
    tag_data: QuestionTagsCreate,
    session: SessionDep,
) -> list[QuestionTagResponse]:
    """Add one or more tags to a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    tag_ids = tag_data.tag_ids
    if not tag_ids:
        raise HTTPException(status_code=400, detail="No tag IDs provided")

    results = []
    for tag_id in tag_ids:
        # Check if tag exists
        tag = session.get(Tag, tag_id)
        if not tag:
            continue  # Skip non-existent tags

        # Check if relationship already exists
        existing_query = select(QuestionTag).where(
            QuestionTag.question_id == question_id, QuestionTag.tag_id == tag_id
        )
        existing = session.exec(existing_query).first()
        if existing and existing.id is not None and existing.created_date is not None:
            results.append(
                QuestionTagResponse(
                    id=existing.id,
                    question_id=existing.question_id,
                    tag_id=existing.tag_id,
                    tag_name=tag.name,
                    created_date=existing.created_date,
                )
            )
            continue

        # Create new relationship
        question_tag = QuestionTag(
            question_id=question_id,
            tag_id=tag_id,
        )
        session.add(question_tag)
        session.flush()  # Flush to get the ID before commit

        # Ensure we have valid ID after flush
        if question_tag.id is not None and question_tag.created_date is not None:
            results.append(
                QuestionTagResponse(
                    id=question_tag.id,
                    question_id=question_tag.question_id,
                    tag_id=question_tag.tag_id,
                    tag_name=tag.name,
                    created_date=question_tag.created_date,
                )
            )

    session.commit()
    return results


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

    # Find the tag
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Find the question-tag relationship
    question_tag_query = select(QuestionTag).where(
        QuestionTag.question_id == question_id, QuestionTag.tag_id == tag_id
    )
    question_tag = session.exec(question_tag_query).first()

    if not question_tag:
        raise HTTPException(
            status_code=404, detail="Tag not associated with this question"
        )

    # Delete the relationship
    session.delete(question_tag)
    session.commit()

    return Message(message="Tag removed from question successfully")


@router.delete("/{question_id}/tags", response_model=Message)
def remove_question_tags(
    question_id: int,
    session: SessionDep,
    tag_ids: list[int] = Query(..., description="Tag IDs to remove"),
) -> Message:
    """Remove multiple tags from a question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    if not tag_ids:
        raise HTTPException(status_code=400, detail="No tag IDs provided")

    deleted_count = 0
    for tag_id in tag_ids:
        # Find the question-tag relationship
        question_tag_query = select(QuestionTag).where(
            QuestionTag.question_id == question_id, QuestionTag.tag_id == tag_id
        )
        question_tag = session.exec(question_tag_query).first()

        if question_tag:
            session.delete(question_tag)
            deleted_count += 1

    session.commit()
    return Message(message=f"Removed {deleted_count} tag(s) from question successfully")


@router.post("/bulk-upload", response_model=Message)
async def upload_questions_csv(
    session: SessionDep, file: UploadFile = File(...), user_id: int = Form(...)
) -> Message:
    """
    Bulk upload questions from a CSV file.
    The CSV should include columns:
    - Questions: The question text
    - Option A, Option B, Option C, Option D: The options
    - Correct Option: Which option is correct (A, B, C, D)
    - Training Tags: Comma-separated list of tags (optional) of the form tag_type:tag_name
    - State: State name or comma-separated list of states (optional)
    """
    # Verify user exists
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify organization exists
    organization_id = user.organization_id
    organization = session.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Save the uploaded file to a temporary file
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    try:
        # Process the CSV content
        csv_text = content.decode("utf-8")

        # Check if CSV is just whitespace
        if not csv_text.strip():
            raise HTTPException(status_code=400, detail="CSV file is empty")

        csv_reader = csv.DictReader(StringIO(csv_text))

        # Check required columns
        required_columns = [
            "Questions",
            "Option A",
            "Option B",
            "Option C",
            "Option D",
            "Correct Option",
        ]
        first_row = next(csv_reader, None)

        if not first_row:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        for column in required_columns:
            if column not in first_row:
                raise HTTPException(
                    status_code=400, detail=f"Missing required column: {column}"
                )

        # Reset the reader
        csv_reader = csv.DictReader(StringIO(csv_text))

        # Start processing rows
        questions_created = 0
        questions_failed = 0
        tag_cache: dict[str, int] = {}  # Cache for tag lookups
        state_cache: dict[str, int] = {}  # Cache for state lookups
        failed_states = set()
        failed_tagtypes = set()

        for row in csv_reader:
            try:
                # Skip empty rows
                if not row.get("Questions", "").strip():
                    continue

                # Extract data
                question_text = row.get("Questions", "").strip()
                options = [
                    row.get("Option A", "").strip(),
                    row.get("Option B", "").strip(),
                    row.get("Option C", "").strip(),
                    row.get("Option D", "").strip(),
                ]

                # Convert option letter to index
                correct_letter = row.get("Correct Option", "A").strip()
                letter_map = {"A": 1, "B": 2, "C": 3, "D": 4}
                correct_answer = letter_map.get(correct_letter, 1)

                valid_options = [
                    {"id": letter_map[key], "key": key, "value": value}
                    for key, value in zip(letter_map.keys(), options, strict=True)
                ]
                print("The valid options are:", valid_options)
                # Process tags if present
                tag_ids = []
                tagtype_error = False
                if "Training Tags" in row and row["Training Tags"].strip():
                    tag_entries = [
                        t.strip() for t in row["Training Tags"].split("|") if t.strip()
                    ]

                    for tag_entry in tag_entries:
                        # Split by colon to get tag_type and tag_name
                        parts = tag_entry.split(":", 1)
                        if len(parts) == 2:
                            tag_type_name = parts[0].strip()
                            tag_name = parts[1].strip()
                        else:
                            # Default tag type if no colon present
                            tag_type_name = "Training Tag"
                            tag_name = tag_entry

                        cache_key = f"{tag_type_name}:{tag_name}"
                        if cache_key in tag_cache:
                            tag_ids.append(tag_cache[cache_key])
                            continue

                        tag_type_query = select(TagType).where(
                            TagType.name == tag_type_name,
                            TagType.organization_id == organization_id,
                        )

                        tag_type = session.exec(tag_type_query).first()

                        if not tag_type:
                            failed_tagtypes.add(tag_type_name)
                            tagtype_error = True
                            continue

                        if tag_type and tag_type.id:
                            # Get or create tag
                            tag_query = select(Tag).where(
                                Tag.name == tag_name,
                                Tag.tag_type_id == tag_type.id,
                                Tag.organization_id == organization_id,
                            )
                            tag = session.exec(tag_query).first()

                            if not tag:
                                tag = Tag(
                                    name=tag_name,
                                    description=f"Tag for {tag_name}",
                                    tag_type_id=tag_type.id,
                                    created_by_id=user_id,
                                    organization_id=organization_id,
                                )
                                session.add(tag)
                                session.flush()

                            if tag and tag.id:
                                tag_ids.append(tag.id)
                                tag_cache[f"{tag_type_name}:{tag_name}"] = tag.id

                if tagtype_error:
                    questions_failed += 1
                    continue

                # Process state information if present
                row_state_ids = []
                state_error = False

                if "State" in row and row["State"].strip():
                    state_names = [
                        s.strip() for s in row["State"].split(",") if s.strip()
                    ]

                    for state_name in state_names:
                        if state_name in state_cache:
                            if state_cache[state_name] not in row_state_ids:
                                row_state_ids.append(state_cache[state_name])
                            continue

                        # Get or create state
                        state_query = select(State).where(State.name == state_name)
                        state = session.exec(state_query).first()

                        if not state:
                            failed_states.add(state_name)
                            state_error = True
                            continue

                        if state and state.id:
                            row_state_ids.append(state.id)
                            state_cache[state_name] = state.id

                # Skip this question if states weren't found
                if state_error:
                    questions_failed += 1
                    continue

                # Create QuestionCreate object
                question_create = QuestionCreate(
                    organization_id=organization_id,
                    created_by_id=user_id,
                    question_text=question_text,
                    question_type="single-choice",  # Assuming single choice questions
                    options=valid_options,
                    correct_answer=[correct_answer],
                    is_mandatory=True,
                    marking_scheme={"correct": 1, "wrong": 0, "skipped": 0},
                    state_ids=row_state_ids,
                    district_ids=[],
                    block_ids=[],
                    tag_ids=tag_ids,
                )

                # Create the question using existing function logic
                question = Question(
                    organization_id=question_create.organization_id,
                )
                session.add(question)
                session.flush()

                # Prepare data for JSON serialization
                options, marking_scheme, media = prepare_for_db(question_create)  # type: ignore

                # Create the revision with serialized data
                revision = QuestionRevision(
                    question_id=question.id,
                    created_by_id=question_create.created_by_id,
                    question_text=question_create.question_text,
                    instructions=question_create.instructions,
                    question_type=question_create.question_type,
                    options=options,
                    correct_answer=question_create.correct_answer,
                    subjective_answer_limit=question_create.subjective_answer_limit,
                    is_mandatory=question_create.is_mandatory,
                    marking_scheme=marking_scheme,
                    solution=question_create.solution,
                    media=media,
                )
                session.add(revision)
                session.flush()

                question.last_revision_id = revision.id

                # Handle state associations
                if question_create.state_ids:
                    for state_id in question_create.state_ids:
                        state_location = QuestionLocation(
                            question_id=question.id,
                            state_id=state_id,
                            district_id=None,
                            block_id=None,
                        )
                        session.add(state_location)

                if question_create.tag_ids:
                    for tag_id in question_create.tag_ids:
                        tag = session.get(Tag, tag_id)
                        if tag:
                            question_tag = QuestionTag(
                                question_id=question.id,
                                tag_id=tag_id,
                            )
                            session.add(question_tag)

                questions_created += 1

            except Exception as e:
                questions_failed += 1
                # Optionally log the error
                print(f"Error processing row: {str(e)}")
                continue

        # Commit all changes at once
        session.commit()

        # Include information about failed states in the response
        message = f"Bulk upload complete. Created {questions_created} questions successfully. Failed to create {questions_failed} questions."
        if failed_states:
            message += f" The following states were not found in the system: {', '.join(failed_states)}"
        if failed_tagtypes:
            message += (
                f" The following tag types were not found: {', '.join(failed_tagtypes)}"
            )

        return Message(message=message)

    except HTTPException:
        # Re-raise any HTTP exceptions we explicitly raised
        raise
    except Exception as e:
        # Handle overall process errors
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
