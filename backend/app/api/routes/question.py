import base64
import csv
import re
from datetime import datetime
from io import StringIO
from typing import Any, cast

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi_pagination import Page, paginate
from sqlalchemy import desc, func
from sqlmodel import col, not_, or_, select
from typing_extensions import TypedDict

from app.api.deps import CurrentUser, Pagination, SessionDep
from app.models import (
    CandidateTest,
    Message,
    Organization,
    Question,
    QuestionCreate,
    QuestionLocation,
    QuestionLocationPublic,
    QuestionLocationsUpdate,
    QuestionPublic,
    QuestionRevision,
    QuestionRevisionCreate,
    QuestionTag,
    QuestionTagsUpdate,
    QuestionUpdate,
    State,
    Tag,
    TagPublic,
    TagType,
    Test,
    User,
)
from app.models.question import BulkUploadQuestionsResponse, Option
from app.models.utils import MarkingScheme

router = APIRouter(prefix="/questions", tags=["Questions"])


def get_tag_type_by_id(session: SessionDep, tag_type_id: int | None) -> TagType | None:
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

    marking_scheme_dict = revision.marking_scheme if revision.marking_scheme else None

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
                tag_type=get_tag_type_by_id(session, tag_type_id=tag.tag_type_id)
                if tag.tag_type_id
                else None,
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
) -> tuple[list[Option] | None, MarkingScheme | None, dict[str, Any] | None]:
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

    marking_scheme: MarkingScheme | None = None
    marking_scheme = data.marking_scheme if data.marking_scheme else None

    # Handle media
    media: dict[str, Any] | None = None
    if data.media and hasattr(data.media, "dict") and callable(data.media.dict):
        media = data.media.dict()
    else:
        media = data.media

    return options, marking_scheme, media


def is_duplicate_question(
    session: SessionDep, question_text: str, tag_ids: list[int] | None
) -> bool:
    normalized_text = re.sub(r"\s+", " ", question_text.strip().lower())
    existing_questions = session.exec(
        select(Question)
        .where(not_(Question.is_deleted))
        .join(QuestionRevision)
        .where(Question.last_revision_id == QuestionRevision.id)
        .where(
            func.lower(
                func.regexp_replace(QuestionRevision.question_text, r"\s+", " ", "g")
            )
            == normalized_text,
        )
    ).all()
    new_tag_ids = set(tag_ids or [])
    for question in existing_questions:
        existing_tag_ids = {
            qt.tag_id
            for qt in session.exec(
                select(QuestionTag).where(QuestionTag.question_id == question.id)
            ).all()
        }
        if not new_tag_ids and not existing_tag_ids or new_tag_ids & existing_tag_ids:
            return True
    return False


@router.post("/", response_model=QuestionPublic)
def create_question(
    question_create: QuestionCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> QuestionPublic:
    """Create a new question with its initial revision, optional location, and tags."""
    if is_duplicate_question(
        session, question_create.question_text, question_create.tag_ids
    ):
        raise HTTPException(
            status_code=400,
            detail="Duplicate question: Same question text and tags already exist.",
        )
    # Create the main question record
    question = Question(
        organization_id=question_create.organization_id,
        is_active=question_create.is_active,
    )
    session.add(question)
    session.flush()

    # Prepare data for JSON serialization
    options, marking_scheme, media = prepare_for_db(question_create)

    revision = QuestionRevision(
        question_id=question.id,
        created_by_id=current_user.id,
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
        is_active=question_create.is_active,
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
    is_deleted: bool
    question_text: str
    instructions: str | None
    question_type: str
    options: list[Option] | None
    correct_answer: Any
    subjective_answer_limit: int | None
    is_mandatory: bool
    marking_scheme: MarkingScheme | None  # Updated type to float
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


@router.get("/", response_model=Page[QuestionPublic])
def get_questions(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    question_text: str | None = None,
    state_ids: list[int] = Query(None),  # Support multiple states
    district_ids: list[int] = Query(None),  # Support multiple districts
    block_ids: list[int] = Query(None),  # Support multiple blocks
    tag_ids: list[int] = Query(None),  # Support multiple tags
    tag_type_ids: list[int] = Query(None),  # Support multiple tag types
    created_by_id: int | None = None,
    is_active: bool | None = None,
    is_deleted: bool = False,  # Default to showing non-deleted questions
) -> Page[QuestionPublic]:
    """Get all questions with optional filtering."""
    # Start with a basic query

    query = select(Question).where(
        Question.organization_id == current_user.organization_id
    )
    if question_text:
        query = query.join(QuestionRevision).where(
            Question.last_revision_id == QuestionRevision.id
        )
        query = query.where(
            func.lower(QuestionRevision.question_text).contains(question_text.lower())
        )

    # Apply filters only if they're provided
    if is_deleted is not None:
        query = query.where(Question.is_deleted == is_deleted)

    if is_active is not None:
        query = query.where(Question.is_active == is_active)

    # Handle tag-based filtering with multiple tags
    if tag_ids:
        tag_query = select(QuestionTag.question_id).where(
            col(QuestionTag.tag_id).in_(tag_ids)
        )
        question_ids_with_tags = session.exec(tag_query).all()
        if question_ids_with_tags:
            query = query.where(col(Question.id).in_(question_ids_with_tags))
        else:
            return cast(Page[QuestionPublic], paginate([], params))

    if tag_type_ids:
        tag_type_query = (
            select(QuestionTag.question_id)
            .join(Tag)
            .where(Tag.id == QuestionTag.tag_id)
            .where(col(Tag.tag_type_id).in_(tag_type_ids))
        )
        question_ids_with_tag_types = session.exec(tag_type_query).all()
        if question_ids_with_tag_types:
            query = query.where(col(Question.id).in_(question_ids_with_tag_types))
        else:
            return cast(Page[QuestionPublic], paginate([], params))

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
            return cast(Page[QuestionPublic], paginate([], params))

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
                return cast(Page[QuestionPublic], paginate([], params))

    # Apply pagination
    # query = query.offset(skip).limit(limit)

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

    return cast(Page[QuestionPublic], paginate(result, params))


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
    current_user: CurrentUser,
) -> QuestionPublic:
    """Create a new revision for an existing question."""
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Prepare data for JSON serialization
    options, marking_scheme, media = prepare_for_db(revision_data)

    new_revision = QuestionRevision(
        question_id=question_id,
        created_by_id=current_user.id,
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
        is_active=revision_data.is_active,
    )
    session.add(new_revision)
    session.flush()

    question.last_revision_id = new_revision.id
    question.is_active = revision_data.is_active
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

    marking_scheme_dict = revision.marking_scheme if revision.marking_scheme else None

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


@router.put("/{question_id}/locations", response_model=list[QuestionLocationPublic])
def update_question_locations(
    question_id: int,
    location_data: QuestionLocationsUpdate,
    session: SessionDep,
) -> list[QuestionLocationPublic]:
    """
    Update all locations for a question by syncing the provided list.
    This will add new locations and remove any existing ones not in the list.
    """
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Get current locations
    current_locations_query = select(QuestionLocation).where(
        QuestionLocation.question_id == question_id
    )
    current_locations = session.exec(current_locations_query).all()
    current_location_set = {
        (loc.state_id, loc.district_id, loc.block_id): loc for loc in current_locations
    }

    # Get desired locations from the request
    desired_location_set = {
        (
            loc.state_id,
            loc.district_id,
            loc.block_id,
        )
        for loc in location_data.locations
    }

    # Determine locations to remove
    locations_to_remove = [
        loc
        for key, loc in current_location_set.items()
        if key not in desired_location_set
    ]
    for loc in locations_to_remove:
        session.delete(loc)

    # Determine locations to add
    current_simple_set = set(current_location_set.keys())
    for loc_item in location_data.locations:
        key = (loc_item.state_id, loc_item.district_id, loc_item.block_id)
        if key not in current_simple_set:
            new_location = QuestionLocation(
                question_id=question_id,
                state_id=loc_item.state_id,
                district_id=loc_item.district_id,
                block_id=loc_item.block_id,
            )
            session.add(new_location)

    session.commit()

    # Return the new state of locations
    final_locations_query = select(QuestionLocation).where(
        QuestionLocation.question_id == question_id
    )
    final_locations = session.exec(final_locations_query).all()
    return [
        QuestionLocationPublic.model_validate(loc, from_attributes=True)
        for loc in final_locations
    ]


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


@router.put("/{question_id}/tags", response_model=list[TagPublic])
def update_question_tags(
    question_id: int,
    tag_data: QuestionTagsUpdate,
    session: SessionDep,
) -> list[TagPublic]:
    """
    Update all tags for a question by syncing the provided list of tag IDs.
    This will add new tags and remove any existing ones not in the list.
    """
    question = session.get(Question, question_id)
    if not question or question.is_deleted:
        raise HTTPException(status_code=404, detail="Question not found")

    # Get current tags
    current_tags_query = select(QuestionTag).where(
        QuestionTag.question_id == question_id
    )
    current_tags = session.exec(current_tags_query).all()
    current_tag_ids = {qt.tag_id for qt in current_tags}

    # Get desired tags from the request
    desired_tag_ids = set(tag_data.tag_ids)

    # Determine tags to remove
    tags_to_remove_ids = current_tag_ids - desired_tag_ids
    if tags_to_remove_ids:
        for qt in current_tags:
            if qt.tag_id in tags_to_remove_ids:
                session.delete(qt)

    # Determine tags to add
    tags_to_add_ids = desired_tag_ids - current_tag_ids
    for tag_id in tags_to_add_ids:
        # Optional: Check if tag exists
        tag = session.get(Tag, tag_id)
        if tag:
            question_tag = QuestionTag(question_id=question_id, tag_id=tag_id)
            session.add(question_tag)

    session.commit()

    # Return the new list of tags for the question
    return get_question_tags(question_id=question_id, session=session)


@router.post("/bulk-upload", response_model=BulkUploadQuestionsResponse)
async def upload_questions_csv(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> BulkUploadQuestionsResponse:
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
    user_id = current_user.id
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify organization exists
    organization_id = current_user.organization_id
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
        failed_question_details = []
        tag_cache: dict[str, int] = {}  # Cache for tag lookups
        state_cache: dict[str, int] = {}  # Cache for state lookups
        failed_states = set()
        failed_tagtypes = set()

        for row_number, row in enumerate(csv_reader, start=1):
            try:
                # Skip empty rows
                if not row.get("Questions", "").strip():
                    raise ValueError("Question text is missing.")

                # Extract data
                question_text = row.get("Questions", "").strip()
                options = [
                    row.get("Option A", "").strip(),
                    row.get("Option B", "").strip(),
                    row.get("Option C", "").strip(),
                    row.get("Option D", "").strip(),
                ]
                if not all(options):
                    raise ValueError("One or more options (A-D) are missing.")
                # Convert option letter to index
                correct_letter = (row.get("Correct Option") or "").strip().upper()
                if not correct_letter:
                    raise ValueError("Correct option is missing.")
                letter_map = {"A": 1, "B": 2, "C": 3, "D": 4}
                if correct_letter not in letter_map:
                    raise ValueError(f"Invalid correct option: {correct_letter}")
                correct_answer = letter_map[correct_letter]

                valid_options = [
                    {"id": letter_map[key], "key": key, "value": value}
                    for key, value in zip(letter_map.keys(), options, strict=True)
                ]
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
                            tag_type_name = None
                            tag_name = tag_entry

                        cache_key = f"{tag_type_name}:{tag_name}"
                        if cache_key in tag_cache:
                            tag_ids.append(tag_cache[cache_key])
                            continue
                        tag_type = None
                        if tag_type_name:
                            tag_type_query = select(TagType).where(
                                TagType.name == tag_type_name,
                                TagType.organization_id == organization_id,
                            )

                            tag_type = session.exec(tag_type_query).first()

                        if tag_type_name and not tag_type:
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
                        else:
                            tag_query = select(Tag).where(
                                Tag.name == tag_name,
                                Tag.tag_type_id is None,
                                Tag.organization_id == organization_id,
                            )
                        tag = session.exec(tag_query).first()

                        if not tag:
                            tag = Tag(
                                name=tag_name,
                                description=f"Tag for {tag_name}",
                                tag_type_id=tag_type.id if tag_type else None,
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
                    failed_question_details.append(
                        {
                            "row_number": row_number,
                            "question_text": question_text,
                            "error": f"Invalid tag types: {', '.join(failed_tagtypes)}",
                        }
                    )
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
                    failed_question_details.append(
                        {
                            "row_number": row_number,
                            "question_text": question_text,
                            "error": f"Invalid states: {', '.join(failed_states)}",
                        }
                    )
                    continue
                if is_duplicate_question(session, question_text, tag_ids):
                    raise ValueError("Questions Already Exist")

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
                    created_by_id=user_id,
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
                failed_question_details.append(
                    {
                        "row_number": row_number,
                        "question_text": row.get("Questions", "").strip(),
                        "error": str(e),
                    }
                )
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
        if questions_failed > 0:
            csv_buffer = StringIO()
            csv_writer = csv.DictWriter(
                csv_buffer, fieldnames=["row_number", "question_text", "error"]
            )
            csv_writer.writeheader()
            for row in failed_question_details:
                csv_writer.writerow(row)
            csv_buffer.seek(0)
            csv_bytes = csv_buffer.getvalue().encode("utf-8")
            base64_csv = base64.b64encode(csv_bytes).decode("utf-8")
            data_link = f"data:text/csv;base64,{base64_csv}"
            failed_message = f"Download failed questions: {data_link}"
        else:
            failed_message = "No failed questions. No CSV generated."

        return BulkUploadQuestionsResponse(
            message=message,
            uploaded_questions=questions_created + questions_failed,
            success_questions=questions_created,
            failed_questions=questions_failed,
            failed_question_details=failed_message,
        )
    except HTTPException:
        # Re-raise any HTTP exceptions we explicitly raised
        raise
    except Exception as e:
        # Handle overall process errors
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
