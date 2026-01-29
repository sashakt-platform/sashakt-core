from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy.orm import selectinload
from sqlmodel import col, exists, func, or_, select

from app.api.deps import (
    CurrentUser,
    Pagination,
    SessionDep,
    permission_dependency,
)
from app.api.routes.utils import get_current_time
from app.core.roles import state_admin, test_admin
from app.core.sorting import (
    SortingParams,
    SortOrder,
    TestSortConfig,
    create_sorting_dependency,
)
from app.models import (
    Block,
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
from app.models.entity import Entity
from app.models.location import District
from app.models.role import Role
from app.models.tag import Tag, TagPublic
from app.models.test import (
    DeleteTest,
    EntityPublicLimited,
    MarksLevelEnum,
    TagRandomCreate,
    TagRandomPublic,
    TestDistrict,
)
from app.models.user import User
from app.models.utils import TimeLeft

router = APIRouter(prefix="/test", tags=["Test"])

# create sorting dependency
TestSorting = create_sorting_dependency(TestSortConfig)
TestSortingDep = Annotated[SortingParams, Depends(TestSorting)]


def check_test_permission(
    session: SessionDep,
    current_user: CurrentUser,
    test: Test,
    *,
    cached_user_location_ids: set[int] | None = None,
    cached_user_location_level: Literal["state", "district"] | None = None,
) -> None:
    """Check if the current user has permission to modify the test.
    A district level user can only modify tests of same district.
    A state level user can only modify tests of same state."""

    user_location_level: Literal["state", "district"] | None = None
    user_location_ids: set[int] | None = None
    exception_message = "State/test-admin cannot modify/delete general tests or tests outside their location."

    if cached_user_location_level and cached_user_location_ids:
        user_location_level = cached_user_location_level
        user_location_ids = cached_user_location_ids
    else:
        if len(current_user.districts) > 0:
            user_location_level = "district"
            user_location_ids = {
                district.id
                for district in current_user.districts
                if district.id is not None
            }
        elif len(current_user.states) > 0:
            user_location_level = "state"
            user_location_ids = {
                state.id for state in current_user.states if state.id is not None
            }
    # If the user has no scoped locations, deny (matches “cannot modify general/out of scope”)
    if not user_location_level or not user_location_ids:
        raise HTTPException(
            403,
            exception_message,
        )
    test_district_ids: set[int] = set()
    test_state_ids: set[int] = set()

    if user_location_level == "district":
        district_rows = session.exec(
            select(TestDistrict.district_id).where(TestDistrict.test_id == test.id)
        ).all()
        for row in district_rows:
            district_id = row[0] if isinstance(row, tuple) else row
            if district_id is not None:
                test_district_ids.add(int(district_id))

        district_out_of_scope = (not test_district_ids) or (
            not test_district_ids.issubset(user_location_ids)
        )
        if district_out_of_scope:
            raise HTTPException(
                403,
                exception_message,
            )
    else:
        state_rows = session.exec(
            select(TestState.state_id).where(TestState.test_id == test.id)
        ).all()
        for row in state_rows:
            state_id = row[0] if isinstance(row, tuple) else row
            if state_id is not None:
                test_state_ids.add(int(state_id))
        # also include states derived from test districts
        district_state_rows = session.exec(
            select(District.state_id)
            .join(TestDistrict, TestDistrict.district_id == District.id)
            .where(TestDistrict.test_id == test.id)
        ).all()
        for row in district_state_rows:
            district_state_id = row[0] if isinstance(row, tuple) else row
            if district_state_id is not None:
                test_state_ids.add(int(district_state_id))
        state_out_of_scope = (not test_state_ids) or (
            not test_state_ids.issubset(user_location_ids)
        )
        if state_out_of_scope:
            raise HTTPException(
                403,
                exception_message,
            )


def add_test_to_failure_list(
    session: SessionDep, test: Test, failure_list: list[TestPublic]
) -> None:
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

    failure_list.append(
        TestPublic(
            **test.model_dump(),
            tags=tags,
            question_revisions=question_revisions,
            states=states,
            districts=districts,
        )
    )


def check_linked_question(session: SessionDep, test_id: int) -> bool:
    query = select(
        exists().where(
            col(CandidateTestAnswer.candidate_test_id).in_(
                select(CandidateTest.id).where(CandidateTest.test_id == test_id)
            )
        )
    )
    result = session.scalar(query)
    return bool(result)


def build_random_tag_public(
    session: SessionDep,
    tag_count_mapping: list[TagRandomCreate],
) -> list[TagRandomPublic]:
    out: list[TagRandomPublic] = []
    for tag_count in tag_count_mapping or []:
        tag = session.get(Tag, tag_count.get("tag_id"))
        if not tag:
            continue
        count = max(int(tag_count.get("count") or 0), 0)
        out.append(TagRandomPublic(tag=TagPublic.model_validate(tag), count=count))
    return out


def transform_tests_to_public(
    session: SessionDep, tests: list[Test] | Any
) -> list[TestPublic]:
    """
    Transform a list of Test objects to TestPublic objects with all nested relationships.
    """
    result: list[TestPublic] = []

    # cast to proper type since fastapi-pagination might return Sequence[Any]
    test_list: list[Test] = list(tests) if not isinstance(tests, list) else tests

    for test in test_list:
        tags = test.tags or []
        question_revisions = test.question_revisions or []
        states = test.states or []
        districts = test.districts or []

        random_tag_public: list[TagRandomPublic] | None = None
        if test.random_tag_count:
            random_tag_public = build_random_tag_public(session, test.random_tag_count)

        # calculate total questions
        total_questions = 0
        if test.random_questions and test.no_of_random_questions:
            total_questions = test.no_of_random_questions
        else:
            total_questions = len(question_revisions)

        if test.random_tag_count:
            total_questions += sum(
                tag_rule.get("count", 0) for tag_rule in test.random_tag_count
            )

        # build TestPublic object
        test_public = TestPublic(
            **test.model_dump(),
            tags=tags,
            question_revisions=question_revisions,
            states=states,
            districts=districts,
            total_questions=total_questions,
            random_tag_counts=random_tag_public,
        )
        result.append(test_public)

    return result


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
    if not test or test.is_active is False:
        raise HTTPException(status_code=404, detail="Test not found or not active")
    current_time = get_current_time()
    if test.end_time is not None and test.end_time < current_time:
        raise HTTPException(status_code=400, detail="Test has already ended")
    profile_list: list[EntityPublicLimited] = []
    if test.candidate_profile:
        query = select(Entity).where(col(Entity.is_active).is_(True))
        district_query = select(TestDistrict.district_id).where(
            TestDistrict.test_id == test.id
        )
        district_ids = session.exec(district_query).all()

        if district_ids:
            query = query.where(col(Entity.district_id).in_(district_ids))
        else:
            state_query = select(TestState.state_id).where(TestState.test_id == test.id)
            state_ids = session.exec(state_query).all()
            if state_ids:
                query = query.where(col(Entity.state_id).in_(state_ids))

        entities = session.exec(query).all()

        entity_block_ids = {e.block_id for e in entities if e.block_id is not None}
        entity_state_ids = {e.state_id for e in entities if e.state_id is not None}
        entity_district_ids = {
            e.district_id for e in entities if e.district_id is not None
        }

        blocks_by_id = (
            {
                b.id: b
                for b in session.exec(
                    select(Block).where(col(Block.id).in_(entity_block_ids))
                ).all()
            }
            if entity_block_ids
            else {}
        )
        states_by_id = (
            {
                s.id: s
                for s in session.exec(
                    select(State).where(col(State.id).in_(entity_state_ids))
                ).all()
            }
            if entity_state_ids
            else {}
        )
        districts_by_id = (
            {
                d.id: d
                for d in session.exec(
                    select(District).where(col(District.id).in_(entity_district_ids))
                ).all()
            }
            if entity_district_ids
            else {}
        )

        for entity in entities:
            block = blocks_by_id.get(entity.block_id)
            state = states_by_id.get(entity.state_id)
            district = districts_by_id.get(entity.district_id)

            profile_list.append(
                EntityPublicLimited(
                    id=entity.id,
                    name=entity.name,
                    label=f"{entity.name} - ({block.name})" if block else entity.name,
                    state=state,
                    district=district,
                    block=block,
                )
            )

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
        **test.model_dump(), total_questions=total_questions, profile_list=profile_list
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
    test_data["organization_id"] = current_user.organization_id
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
    random_tag_public: list[TagRandomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = build_random_tag_public(session, test.random_tag_count)

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
    sorting: TestSortingDep,
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
) -> Page[TestPublic]:
    query = (
        select(Test)
        .options(
            selectinload(Test.tags),  # type: ignore[arg-type]
            selectinload(Test.question_revisions),  # type: ignore[arg-type]
            selectinload(Test.states),  # type: ignore[arg-type]
            selectinload(Test.districts),  # type: ignore[arg-type]
        )
        .where(Test.organization_id == current_user.organization_id)
    )

    if (
        current_user.role.name == state_admin.name
        or current_user.role.name == test_admin.name
    ):
        current_user_district_ids = (
            [district.id for district in current_user.districts]
            if current_user.districts
            else []
        )
        if current_user_district_ids:
            query = query.outerjoin(TestDistrict).where(
                or_(
                    col(TestDistrict.district_id).is_(None),
                    col(TestDistrict.district_id).in_(current_user_district_ids),
                )
            )
        else:
            current_user_state_ids = (
                [state.id for state in current_user.states]
                if current_user.states
                else []
            )
            if current_user_state_ids:
                query = query.outerjoin(TestState).where(
                    or_(
                        col(TestState.state_id).is_(None),
                        col(TestState.state_id).in_(current_user_state_ids),
                    )
                )

    # apply default sorting if no sorting was specified
    sorting_with_default = sorting.apply_default_if_none(
        "modified_date", SortOrder.DESC
    )
    query = sorting_with_default.apply_to_query(query, TestSortConfig)

    # apply filters only if they're provided
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
        tag_subquery = (
            select(TestTag.test_id).where(col(TestTag.tag_id).in_(tag_ids)).distinct()
        )
        query = query.where(col(Test.id).in_(tag_subquery))

    if tag_type_ids:
        tag_subquery = (
            select(TestTag.test_id)
            .join(Tag)
            .where(col(Tag.tag_type_id).in_(tag_type_ids))
            .distinct()
        )
        query = query.where(col(Test.id).in_(tag_subquery))

    if state_ids:
        state_subquery = (
            select(TestState.test_id)
            .where(col(TestState.state_id).in_(state_ids))
            .distinct()
        )
        query = query.where(col(Test.id).in_(state_subquery))

    if district_ids:
        district_subquery = (
            select(TestDistrict.test_id)
            .where(col(TestDistrict.district_id).in_(district_ids))
            .distinct()
        )
        query = query.where(col(Test.id).in_(district_subquery))

    # let's get the tests with custom transformer
    tests: Page[TestPublic] = paginate(
        session,
        query,
        params,
        transformer=lambda items: transform_tests_to_public(session, items),
    )

    return tests


@router.get(
    "/{test_id}",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("read_test"))],
)
def get_test_by_id(test_id: int, session: SessionDep) -> TestPublic:
    test = session.get(Test, test_id)
    if not test:
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
    random_tag_public: list[TagRandomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = build_random_tag_public(session, test.random_tag_count)

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
    current_user: CurrentUser,
) -> TestPublic:
    test = session.get(Test, test_id)

    if not test:
        raise HTTPException(status_code=404, detail="Test is not available")
    role = session.get(Role, current_user.role_id)
    if role and role.name in (state_admin.name, test_admin.name):
        check_test_permission(session, current_user, test)

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
    random_tag_public: list[TagRandomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = build_random_tag_public(session, test.random_tag_count)

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
    if not test:
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
    random_tag_public: list[TagRandomPublic] | None = None
    if test.random_tag_count:
        random_tag_public = build_random_tag_public(session, test.random_tag_count)

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
def delete_test(
    test_id: int, session: SessionDep, current_user: CurrentUser
) -> Message:
    test = session.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test is not available")
    role = session.get(Role, current_user.role_id)
    if role and role.name in (state_admin.name, test_admin.name):
        check_test_permission(session, current_user, test)

    if check_linked_question(session, test_id):
        raise HTTPException(
            status_code=422,
            detail="Cannot delete test. One or more answers have already been submitted for its questions.",
        )

    session.delete(test)
    session.commit()

    return Message(message="Test deleted successfully")


@router.delete(
    "/",
    response_model=DeleteTest,
    dependencies=[Depends(permission_dependency("delete_test"))],
)
def bulk_delete_question(
    session: SessionDep, current_user: CurrentUser, test_ids: list[int] = Body(...)
) -> DeleteTest:
    """bulk delete test"""
    success_count = 0
    failure_list: list[TestPublic] = []

    current_user_org_id = current_user.organization_id

    db_test = session.exec(
        select(Test)
        .join(User)
        .where(Test.created_by_id == User.id)
        .where(col(Test.id).in_(test_ids), User.organization_id == current_user_org_id)
    ).all()

    found_ids = {q.id for q in db_test}
    missing_ids = set(test_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404, detail="Invalid Tests selected for deletion"
        )

    role = session.get(Role, current_user.role_id)

    if role and role.name in (state_admin.name, test_admin.name):
        if current_user.states:
            admin_location_ids = {
                state.id for state in current_user.states if state.id is not None
            }
            admin_location_level = "state"
        elif current_user.districts:
            admin_location_ids = {
                state.id for state in current_user.districts if state.id is not None
            }
            admin_location_level = "district"
        else:
            admin_location_ids = None
            admin_location_level = None
    else:
        admin_location_ids = None
        admin_location_level = None
    for test in db_test:
        try:
            if admin_location_ids:
                check_test_permission(
                    session,
                    current_user,
                    test,
                    cached_user_location_ids=admin_location_ids,
                    cached_user_location_level=admin_location_level,
                )

            if test.id is not None and check_linked_question(session, test.id):
                add_test_to_failure_list(session, test, failure_list)
            else:
                session.delete(test)
                success_count += 1

        except HTTPException:
            add_test_to_failure_list(session, test, failure_list)

    session.commit()
    return DeleteTest(
        delete_success_count=success_count, delete_failure_list=failure_list or None
    )


@router.get("/public/time_left/{test_uuid}", response_model=TimeLeft)
def get_time_before_test_start_public(test_uuid: str, session: SessionDep) -> TimeLeft:
    test = session.exec(select(Test).where(Test.link == test_uuid)).first()
    if not test or test.is_active is False:
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
    if not original:
        raise HTTPException(status_code=404, detail="Test not found")

    test_data = original.model_dump(exclude={"id", "created_date", "modified_date"})
    test_data["name"] = f"Copy of {original.name}"
    test_data["created_by_id"] = current_user.id
    test_data["organization_id"] = current_user.organization_id
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
    random_tag_public: list[TagRandomPublic] | None = None
    if new_test.random_tag_count:
        random_tag_public = build_random_tag_public(session, new_test.random_tag_count)

    return TestPublic(
        **new_test.model_dump(),
        tags=tags,
        question_revisions=question_revisions,
        states=states,
        districts=districts,
        random_tag_counts=random_tag_public,
    )
