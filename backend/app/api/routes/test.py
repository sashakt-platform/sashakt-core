from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_pagination import Page, paginate
from sqlmodel import col, exists, func, select

from app.api.deps import CurrentUser, Pagination, SessionDep, permission_dependency
from app.api.routes.utils import get_current_time
from app.models import (
    Message,
    QuestionRevision,
    State,
    Test,
    TestCreate,
    TestPublic,
    TestPublicLimited,
    TestQuestion,
    TestState,
    TestTag,
    TestUpdate,
)
from app.models.candidate import CandidateTest, CandidateTestAnswer
from app.models.location import District
from app.models.tag import Tag, TagPublic
from app.models.test import MarksLevelEnum, Tag_randomPublic, TestDistrict
from app.models.user import User
from app.models.utils import TimeLeft

router = APIRouter(prefix="/test", tags=["Test"])


def validate_test_time_config(
    start_time: datetime | None, end_time: datetime | None, time_limit: int | None
) -> None:
    if start_time and end_time:
        if end_time <= start_time:
            raise HTTPException(
                status_code=400,
                detail="End time cannot be earlier than start time.",
            )
        if time_limit is not None:
            total_seconds = (end_time - start_time).total_seconds()
            if time_limit * 60 > total_seconds:
                raise HTTPException(
                    status_code=400,
                    detail="Time limit cannot be more than the duration between start and end time.",
                )


# Public endpoint to get basic test information (for landing page)
@router.get("/public/{test_uuid}", response_model=TestPublicLimited)
def get_public_test_info(test_uuid: str, session: SessionDep) -> TestPublicLimited:
    """
    Get public information for a test using its UUID link.
    This endpoint is for the test landing page before starting the test.
    No authentication required.
    """
    test = session.exec(select(Test).where(Test.link == test_uuid)).first()
    if not test or test.is_deleted or test.is_active is False:
        raise HTTPException(status_code=404, detail="Test not found or not active")
    current_time = get_current_time()
    if test.end_time is not None and test.end_time < current_time:
        raise HTTPException(status_code=400, detail="Test has already ended")
    if (
        test.random_questions
        and test.no_of_random_questions is not None
        and test.no_of_random_questions > 0
    ):
        total_questions = test.no_of_random_questions
    else:
        question_revision_query = (
            select(QuestionRevision)
            .join(TestQuestion)
            .where(TestQuestion.test_id == test.id)
        )
        question_revisions = session.exec(question_revision_query).all()
        total_questions = len(question_revisions)

    if test.random_tag_count:
        total_questions += sum(
            tag_rule.get("count", 0) for tag_rule in test.random_tag_count
        )

    return TestPublicLimited(
        **test.model_dump(),
        total_questions=total_questions,
    )


# Create a Test
@router.post(
    "/",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("create_test"))],
)
def create_test(
    test_create: TestCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TestPublic:
    test_data = test_create.model_dump(
        exclude={"tag_ids", "question_revision_ids", "state_ids", "district_ids"}
    )
    test_data["created_by_id"] = current_user.id
    # Auto-generate UUID for link if not provided
    if not test_data["is_template"] and not test_data["link"]:
        import uuid

        test_data["link"] = str(uuid.uuid4())
    validate_test_time_config(
        test_data.get("start_time"),
        test_data.get("end_time"),
        test_data.get("time_limit"),
    )
    test = Test.model_validate(test_data)
    if test.random_questions:
        if test.no_of_random_questions is None or test.no_of_random_questions < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No. of random questions must be provided if random questions are enabled.",
            )
        total_questions = len(test_create.question_revision_ids or [])
        if test.no_of_random_questions > total_questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No. of random questions ({test.no_of_random_questions}) "
                    f"cannot be greater than total questions added ({total_questions})"
                ),
            )

    session.add(test)
    session.commit()
    session.refresh(test)
    random_tag_public: list[Tag_randomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = []
        for tag_count_mapping in test.random_tag_count:
            tag = session.get(Tag, tag_count_mapping["tag_id"])
            if tag:
                random_tag_public.append(
                    Tag_randomPublic(
                        tag=TagPublic.model_validate(tag),
                        count=tag_count_mapping["count"],
                    )
                )

    if test_create.tag_ids:
        tag_ids = test_create.tag_ids
        tag_links = [TestTag(test_id=test.id, tag_id=tag_id) for tag_id in tag_ids]
        session.add_all(tag_links)
        session.commit()

    if test_create.question_revision_ids:
        revision_ids = test_create.question_revision_ids
        question_links = []

        for revision_id in revision_ids:
            # Get the question_id from the revision
            revision = session.get(QuestionRevision, revision_id)
            if revision:
                question_links.append(
                    TestQuestion(
                        test_id=test.id,
                        question_revision_id=revision_id,  # Set question_revision_id
                    )
                )

        session.add_all(question_links)
        session.commit()

    if test_create.state_ids:
        state_ids = test_create.state_ids
        state_links = [
            TestState(test_id=test.id, state_id=state_id) for state_id in state_ids
        ]
        session.add_all(state_links)
        session.commit()
    if test_create.district_ids:
        district_ids = test_create.district_ids
        district_links = [
            TestDistrict(test_id=test.id, district_id=district_id)
            for district_id in district_ids
        ]
        session.add_all(district_links)
        session.commit()

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
    district_query = (
        select(District).join(TestDistrict).where(TestDistrict.test_id == test.id)
    )
    districts = session.exec(district_query).all()

    return TestPublic(
        **test.model_dump(),
        tags=tags,
        question_revisions=question_revisions,
        states=states,
        districts=districts,
        random_tag_counts=random_tag_public,
    )


# Get All Tests
@router.get(
    "/",
    response_model=Page[TestPublic],
    dependencies=[Depends(permission_dependency("read_test"))],
)
def get_test(
    session: SessionDep,
    current_user: CurrentUser,
    params: Pagination = Depends(),
    marks_level: MarksLevelEnum | None = None,
    name: str | None = None,
    description: str | None = None,
    start_time_gte: datetime | None = None,
    start_time_lte: datetime | None = None,
    end_time_gte: datetime | None = None,
    end_time_lte: datetime | None = None,
    time_limit_gte: int | None = None,
    time_limit_lte: int | None = None,
    completion_message: str | None = None,
    start_instructions: str | None = None,
    no_of_attempts: int | None = None,
    no_of_attempts_gte: int | None = None,
    no_of_attempts_lte: int | None = None,
    shuffle: bool | None = None,
    random_questions: bool | None = None,
    no_of_random_questions: int | None = None,
    no_of_random_questions_gte: int | None = Query(None),
    no_of_random_questions_lte: int | None = None,
    question_pagination: int | None = None,
    is_template: bool | None = None,
    created_by: list[int] | None = Query(None),
    tag_ids: list[int] | None = Query(None),
    tag_type_ids: list[int] | None = Query(None),
    state_ids: list[int] | None = Query(None),
    district_ids: list[int] | None = Query(None),
    is_active: bool | None = None,
    is_deleted: bool = False,  # Default to showing non-deleted questions
    order_by: list[str] = Query(
        default=["created_date"],
        title="Order by",
        description="Order by fields",
        examples=["-created_date", "name"],
    ),
) -> Page[TestPublic]:
    query = select(Test).join(User).where(Test.created_by_id == User.id)
    query = query.where(User.organization_id == current_user.organization_id)
    empty_result = cast(Page[TestPublic], paginate([], params))

    for order in order_by:
        is_desc = order.startswith("-")
        order = order.lstrip("-")
        column = getattr(Test, order, None)
        if column is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order_by field: {order}",
            )
        query = query.order_by(column.desc() if is_desc else column)

    # Apply filters only if they're provided

    query = query.where(Test.is_deleted == is_deleted)

    if is_active is not None:
        query = query.where(Test.is_active == is_active)

    if name is not None:
        query = query.where(func.lower(Test.name).like(f"%{name.lower()}%"))

    if description is not None:
        query = query.where(
            func.lower(Test.description).like(f"%{description.lower()}%")
        )

    if completion_message is not None:
        query = query.where(col(Test.completion_message).contains(completion_message))

    if start_instructions is not None:
        query = query.where(col(Test.start_instructions).contains(start_instructions))

    if start_time_gte is not None and Test.start_time is not None:
        query = query.where(Test.start_time >= start_time_gte)
    if start_time_lte is not None and Test.start_time is not None:
        query = query.where(Test.start_time <= start_time_lte)

    if end_time_gte is not None and Test.end_time is not None:
        query = query.where(Test.end_time >= end_time_gte)
    if end_time_lte is not None and Test.end_time is not None:
        query = query.where(Test.end_time <= end_time_lte)

    if time_limit_gte is not None and Test.time_limit is not None:
        query = query.where(Test.time_limit >= time_limit_gte)
    if time_limit_lte is not None and Test.time_limit is not None:
        query = query.where(Test.time_limit <= time_limit_lte)

    if marks_level is not None and Test.marks_level is not None:
        query = query.where(Test.marks_level == marks_level)

    if no_of_attempts is not None and Test.no_of_attempts is not None:
        query = query.where(Test.no_of_attempts == no_of_attempts)

    if no_of_attempts_gte is not None and Test.no_of_attempts is not None:
        query = query.where(Test.no_of_attempts >= no_of_attempts_gte)
    if no_of_attempts_lte is not None and Test.no_of_attempts is not None:
        query = query.where(Test.no_of_attempts <= no_of_attempts_lte)

    if shuffle is not None:
        query = query.where(Test.shuffle == shuffle)

    if random_questions is not None:
        query = query.where(Test.random_questions == random_questions)

    if no_of_random_questions is not None:
        query = query.where(Test.no_of_random_questions == no_of_random_questions)
    if (
        no_of_random_questions_gte is not None
        and Test.no_of_random_questions is not None
    ):
        query = query.where(Test.no_of_random_questions >= no_of_random_questions_gte)
    if (
        no_of_random_questions_lte is not None
        and Test.no_of_random_questions is not None
    ):
        query = query.where(Test.no_of_random_questions <= no_of_random_questions_lte)

    if question_pagination is not None:
        query = query.where(Test.question_pagination == question_pagination)

    if is_template is not None:
        query = query.where(Test.is_template == is_template)

    if created_by is not None:
        query = query.where(col(Test.created_by_id).in_(created_by))
    if tag_ids:
        tag_query = select(TestTag.test_id).where(col(TestTag.tag_id).in_(tag_ids))
        test_ids_with_tags = session.exec(tag_query).all()
        if test_ids_with_tags:
            query = query.where(col(Test.id).in_(test_ids_with_tags))
        else:
            return empty_result
    if tag_type_ids:
        tag_type_query = (
            select(TestTag.test_id)
            .join(Tag)
            .where(Tag.id == TestTag.tag_id)
            .where(col(Tag.tag_type_id).in_(tag_type_ids))
        )
        test_ids_with_tag_types = session.exec(tag_type_query).all()
        if test_ids_with_tag_types:
            query = query.where(col(Test.id).in_(test_ids_with_tag_types))
        else:
            return empty_result

    if state_ids:
        state_subquery = select(TestState.test_id).where(
            col(TestState.state_id).in_(state_ids)
        )
        test_ids_with_states = session.exec(state_subquery).all()
        if test_ids_with_states:
            query = query.where(col(Test.id).in_(test_ids_with_states))
        else:
            return empty_result

    if district_ids:
        district_subquery = select(TestDistrict.test_id).where(
            col(TestDistrict.district_id).in_(district_ids)
        )
        test_ids_with_districts = session.exec(district_subquery).all()
        if test_ids_with_districts:
            query = query.where(col(Test.id).in_(test_ids_with_districts))
        else:
            return empty_result

    # Execute query and get all questions
    tests = session.exec(query).all()

    test_public = []

    for test in tests:
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
        districts_query = (
            select(District).join(TestDistrict).where(TestDistrict.test_id == test.id)
        )
        districts = session.exec(districts_query).all()
        random_tag_public: list[Tag_randomPublic] | None = None
        if test.random_tag_count:
            random_tag_public = []
            for tag_count_mapping in test.random_tag_count:
                tag = session.get(Tag, tag_count_mapping["tag_id"])
                if tag:
                    random_tag_public.append(
                        Tag_randomPublic(
                            tag=TagPublic.model_validate(tag),
                            count=tag_count_mapping["count"],
                        )
                    )

        test_public.append(
            TestPublic(
                **test.model_dump(),
                tags=tags,
                question_revisions=question_revisions,
                states=states,
                districts=districts,
                random_tag_counts=random_tag_public,
            )
        )

    return cast(Page[TestPublic], paginate(test_public, params))


@router.get(
    "/{test_id}",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("read_test"))],
)
def get_test_by_id(test_id: int, session: SessionDep) -> TestPublic:
    test = session.get(Test, test_id)
    if not test or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")

    tags_query = select(Tag).join(TestTag).where(TestTag.test_id == test.id)
    tags = session.exec(tags_query).all()

    question_revision_query = (
        select(QuestionRevision)
        .join(TestQuestion)
        .where(TestQuestion.test_id == test.id)
    )
    question_revisions = session.exec(question_revision_query).all()

    state_query = select(State).join(TestState).where(TestState.test_id == test_id)
    states = session.exec(state_query).all()
    district_query = (
        select(District).join(TestDistrict).where(TestDistrict.test_id == test_id)
    )
    districts = session.exec(district_query).all()
    random_tag_public: list[Tag_randomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = []
        for tag_count_mapping in test.random_tag_count:
            tag = session.get(Tag, tag_count_mapping["tag_id"])
            if tag:
                random_tag_public.append(
                    Tag_randomPublic(
                        tag=TagPublic.model_validate(tag),
                        count=tag_count_mapping["count"],
                    )
                )

    return TestPublic(
        **test.model_dump(),
        tags=tags,
        question_revisions=question_revisions,
        states=states,
        districts=districts,
        random_tag_counts=random_tag_public,
    )


@router.put(
    "/{test_id}",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("update_test"))],
)
def update_test(
    test_id: int,
    test_update: TestUpdate,
    session: SessionDep,
) -> TestPublic:
    test = session.get(Test, test_id)

    if not test or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")
    if (
        test_update.start_time is not None
        or test_update.end_time is not None
        or test_update.time_limit is not None
    ):
        start_time = (
            test_update.start_time
            if test_update.start_time is not None
            else test.start_time
        )
        end_time = (
            test_update.end_time if test_update.end_time is not None else test.end_time
        )
        time_limit = (
            test_update.time_limit
            if test_update.time_limit is not None
            else test.time_limit
        )
        validate_test_time_config(start_time, end_time, time_limit)
    if test_update.random_questions:
        if (
            test_update.no_of_random_questions is None
            or test_update.no_of_random_questions < 1
        ):
            raise HTTPException(
                status_code=400,
                detail="No. of random questions must be provided if random questions are enabled.",
            )
        if (
            test_update.question_revision_ids
            and len(test_update.question_revision_ids) > 0
        ):
            total_questions = len(test_update.question_revision_ids)
        else:
            existing_revision_ids = session.exec(
                select(TestQuestion.question_revision_id).where(
                    TestQuestion.test_id == test_id
                )
            ).all()

            total_questions = len(existing_revision_ids)
        if test_update.no_of_random_questions > total_questions:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No. of random questions ({test_update.no_of_random_questions}) "
                    f"cannot be greater than total questions added ({total_questions})"
                ),
            )

    # Updating Tags
    tags_remove = [
        tag.id for tag in (test.tags or []) if tag.id not in (test_update.tag_ids or [])
    ]
    tags_add = [
        tag
        for tag in (test_update.tag_ids or [])
        if tag not in [t.id for t in (test.tags or [])]
    ]

    if tags_remove:
        for tag in tags_remove:
            session.delete(
                session.exec(
                    select(TestTag).where(
                        TestTag.test_id == test.id, TestTag.tag_id == tag
                    )
                ).one()
            )
            session.commit()

    if tags_add:
        for tag in tags_add:
            session.add(TestTag(test_id=test.id, tag_id=tag))
            session.commit()

    current_revision_ids = session.exec(
        select(TestQuestion.question_revision_id).where(TestQuestion.test_id == test.id)
    ).all()

    new_revision_ids = test_update.question_revision_ids or []

    # Remove questions that aren't in the update
    revision_ids_to_remove = [
        r for r in current_revision_ids if r not in new_revision_ids
    ]
    for revision_id in revision_ids_to_remove:
        session.delete(
            session.exec(
                select(TestQuestion).where(
                    TestQuestion.test_id == test.id,
                    TestQuestion.question_revision_id == revision_id,
                )
            ).one()
        )
        session.commit()

    # Add new question revisions
    revision_ids_to_add = [r for r in new_revision_ids if r not in current_revision_ids]
    for revision_id in revision_ids_to_add:
        # Get the question_id from the revision
        revision = session.get(QuestionRevision, revision_id)
        if revision:
            session.add(TestQuestion(test_id=test.id, question_revision_id=revision_id))
            session.commit()

    # Updating States
    states_remove = [
        state.id
        for state in (test.states or [])
        if state.id not in (test_update.state_ids or [])
    ]
    states_add = [
        state
        for state in (test_update.state_ids or [])
        if state not in [s.id for s in (test.states or [])]
    ]

    if states_remove:
        for state in states_remove:
            session.delete(
                session.exec(
                    select(TestState).where(
                        TestState.test_id == test.id,
                        TestState.state_id == state,
                    )
                ).one()
            )
            session.commit()

    if states_add:
        for state in states_add:
            session.add(TestState(test_id=test.id, state_id=state))
            session.commit()

    districts_remove = [
        district.id
        for district in (test.districts or [])
        if district.id not in (test_update.district_ids or [])
    ]
    districts_add = [
        district
        for district in (test_update.district_ids or [])
        if district not in [d.id for d in (test.districts or [])]
    ]
    if districts_remove:
        for district in districts_remove:
            session.delete(
                session.exec(
                    select(TestDistrict).where(
                        TestDistrict.test_id == test.id,
                        TestDistrict.district_id == district,
                    )
                ).one()
            )
        session.commit()

    if districts_add:
        for district in districts_add:
            session.add(TestDistrict(test_id=test.id, district_id=district))
            session.commit()
    test_data = test_update.model_dump(exclude_unset=True)
    test.sqlmodel_update(test_data)
    session.add(test)
    session.commit()
    session.refresh(test)

    tags_query = select(Tag).join(TestTag).where(TestTag.test_id == test.id)
    tags = session.exec(tags_query).all()

    question_revision_query = (
        select(QuestionRevision)
        .join(TestQuestion)
        .where(TestQuestion.test_id == test.id)
    )
    question_revisions = session.exec(question_revision_query).all()

    state_query = select(State).join(TestState).where(TestState.test_id == test_id)
    states = session.exec(state_query).all()
    district_query = (
        select(District).join(TestDistrict).where(TestDistrict.test_id == test_id)
    )
    districts = session.exec(district_query).all()
    random_tag_public: list[Tag_randomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = []
        for tag_count_mapping in test.random_tag_count:
            tag_obj = session.get(Tag, tag_count_mapping["tag_id"])
            if tag_obj:
                random_tag_public.append(
                    Tag_randomPublic(
                        tag=TagPublic.model_validate(tag_obj),
                        count=tag_count_mapping["count"],
                    )
                )

    return TestPublic(
        **test.model_dump(),
        tags=tags,
        question_revisions=question_revisions,
        states=states,
        districts=districts,
        random_tag_counts=random_tag_public,
    )


@router.patch(
    "/{test_id}",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("update_test"))],
)
def visibility_test(
    test_id: int,
    session: SessionDep,
    is_active: bool = Query(False, description="Set visibility of Test"),
) -> TestPublic:
    test = session.get(Test, test_id)
    if not test or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")

    test.is_active = is_active
    session.add(test)
    session.commit()
    session.refresh(test)

    tags_query = select(Tag).join(TestTag).where(TestTag.test_id == test.id)
    tags = session.exec(tags_query).all()

    question_revision_query = (
        select(QuestionRevision)
        .join(TestQuestion)
        .where(TestQuestion.test_id == test.id)
    )
    question_revisions = session.exec(question_revision_query).all()

    state_query = select(State).join(TestState).where(TestState.test_id == test_id)
    states = session.exec(state_query).all()
    district_query = (
        select(District).join(TestDistrict).where(TestDistrict.test_id == test_id)
    )
    districts = session.exec(district_query).all()
    random_tag_public: list[Tag_randomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = []
        for tag_count_mapping in test.random_tag_count:
            tag_obj = session.get(Tag, tag_count_mapping["tag_id"])
            if tag_obj:
                random_tag_public.append(
                    Tag_randomPublic(
                        tag=TagPublic.model_validate(tag_obj),
                        count=tag_count_mapping["count"],
                    )
                )

    return TestPublic(
        **test.model_dump(),
        tags=tags,
        question_revisions=question_revisions,
        states=states,
        districts=districts,
        random_tag_counts=random_tag_public,
    )


@router.delete(
    "/{test_id}",
    dependencies=[Depends(permission_dependency("delete_test"))],
)
def delete_test(test_id: int, session: SessionDep) -> Message:
    test = session.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test is not available")
    attempted_answer_exists = session.scalar(
        select(
            exists().where(
                col(CandidateTestAnswer.candidate_test_id).in_(
                    select(CandidateTest.id).where(CandidateTest.test_id == test_id)
                )
            )
        )
    )

    if attempted_answer_exists:
        raise HTTPException(
            status_code=422,
            detail="Cannot delete test. One or more answers have already been submitted for its questions.",
        )

    session.delete(test)
    session.commit()

    return Message(message="Test deleted successfully")


@router.get("/public/time_left/{test_uuid}", response_model=TimeLeft)
def get_time_before_test_start_public(test_uuid: str, session: SessionDep) -> TimeLeft:
    test = session.exec(select(Test).where(Test.link == test_uuid)).first()
    if not test or test.is_deleted or test.is_active is False:
        raise HTTPException(status_code=404, detail="Test not found or not active")
    if test.start_time is None:
        return TimeLeft(time_left=0)
    current_time = get_current_time()
    start_time = test.start_time
    if current_time >= start_time:
        return TimeLeft(time_left=0)
    seconds_left = (start_time - current_time).total_seconds()
    return TimeLeft(time_left=int(seconds_left))


@router.post(
    "/{test_id}/clone",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("create_test"))],
)
def clone_test(
    test_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TestPublic:
    # Fetch the original test
    original = session.get(Test, test_id)
    if not original or original.is_deleted:
        raise HTTPException(status_code=404, detail="Test not found")

    test_data = original.model_dump(exclude={"id", "created_date", "modified_date"})
    test_data["name"] = f"Copy of {original.name}"
    test_data["created_by_id"] = current_user.id
    if not original.is_template:
        import uuid

        test_data["link"] = str(uuid.uuid4())

    new_test = Test.model_validate(test_data)
    session.add(new_test)
    session.commit()
    session.refresh(new_test)

    tag_links = session.exec(
        select(TestTag).where(TestTag.test_id == original.id)
    ).all()
    for tag_link in tag_links:
        session.add(TestTag(test_id=new_test.id, tag_id=tag_link.tag_id))
    session.commit()

    question_links = session.exec(
        select(TestQuestion).where(TestQuestion.test_id == original.id)
    ).all()
    for ql in question_links:
        session.add(
            TestQuestion(
                test_id=new_test.id, question_revision_id=ql.question_revision_id
            )
        )
    session.commit()
    state_links = session.exec(
        select(TestState).where(TestState.test_id == original.id)
    ).all()
    for sl in state_links:
        session.add(TestState(test_id=new_test.id, state_id=sl.state_id))
    session.commit()
    district_links = session.exec(
        select(TestDistrict).where(TestDistrict.test_id == original.id)
    ).all()
    for dl in district_links:
        session.add(TestDistrict(test_id=new_test.id, district_id=dl.district_id))
    session.commit()
    district_query = (
        select(District).join(TestDistrict).where(TestDistrict.test_id == new_test.id)
    )
    districts = session.exec(district_query).all()

    tags_query = select(Tag).join(TestTag).where(TestTag.test_id == new_test.id)
    tags = session.exec(tags_query).all()
    question_revision_query = (
        select(QuestionRevision)
        .join(TestQuestion)
        .where(TestQuestion.test_id == new_test.id)
    )
    question_revisions = session.exec(question_revision_query).all()
    state_query = select(State).join(TestState).where(TestState.test_id == new_test.id)
    states = session.exec(state_query).all()
    random_tag_public: list[Tag_randomPublic] | None = None
    if new_test.random_tag_count:
        random_tag_public = []
        for tag_count_mapping in new_test.random_tag_count:
            tag_obj = session.get(Tag, tag_count_mapping["tag_id"])
            if tag_obj:
                random_tag_public.append(
                    Tag_randomPublic(
                        tag=TagPublic.model_validate(tag_obj),
                        count=tag_count_mapping["count"],
                    )
                )

    return TestPublic(
        **new_test.model_dump(),
        tags=tags,
        question_revisions=question_revisions,
        states=states,
        districts=districts,
        random_tag_counts=random_tag_public,
    )
