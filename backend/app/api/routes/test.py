import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
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
from app.api.routes.utils import get_current_time, get_current_user_location_ids
from app.core.question_sets import is_sectioned_test
from app.core.roles import state_admin, test_admin
from app.core.sorting import (
    SortingParams,
    SortOrder,
    TestSortConfig,
    create_sorting_dependency,
)
from app.crud import organization_settings as crud_settings
from app.models import (
    Message,
    QuestionRevision,
    QuestionSet,
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
from app.models.form import Form, FormFieldPublic, FormPublic
from app.models.location import District
from app.models.role import Role
from app.models.tag import Tag, TagPublic
from app.models.test import (
    DeleteTest,
    MarksLevelEnum,
    QuestionSetCreate,
    QuestionSetPublic,
    QuestionSetSummaryPublic,
    QuestionSetUpdate,
    TagRandomCreate,
    TagRandomPublic,
    TestDistrict,
    TestLink,
    TestLinkPublic,
)
from app.models.user import User
from app.models.utils import TimeLeft
from app.services.organization_nomenclature import resolve_nomenclature_for_test
from app.services.organization_settings_mapper import (
    fixed_overrides_for_test,
    get_effective_test_flags,
)

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
        user_location_level, user_location_ids = get_current_user_location_ids(
            current_user
        )
    # If the user has no scoped locations, deny (matches “cannot modify general/out of scope”)
    if not user_location_level or not user_location_ids:
        raise HTTPException(
            403,
            exception_message,
        )
    test_district_ids: set[int] = set()

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
        test_state_ids: set[int] = set()
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
            .join(TestDistrict)
            .where(TestDistrict.district_id == District.id)
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
    failure_list.append(build_test_public_response(session, test))


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


def get_persisted_test_id(test: Test) -> int:
    if test.id is None:
        raise HTTPException(status_code=500, detail="Test is missing a database id.")
    return test.id


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


def get_test_question_links(session: SessionDep, test_id: int) -> list[TestQuestion]:
    return list(
        session.exec(
            select(TestQuestion)
            .where(TestQuestion.test_id == test_id)
            .order_by(col(TestQuestion.id))
        ).all()
    )


def get_test_question_sets(session: SessionDep, test_id: int) -> list[QuestionSet]:
    return list(
        session.exec(
            select(QuestionSet)
            .where(QuestionSet.test_id == test_id)
            .order_by(col(QuestionSet.display_order), col(QuestionSet.id))
        ).all()
    )


def get_question_revisions_map(
    session: SessionDep, question_revision_ids: list[int]
) -> dict[int, QuestionRevision]:
    if not question_revision_ids:
        return {}
    question_revisions = session.exec(
        select(QuestionRevision).where(
            col(QuestionRevision.id).in_(question_revision_ids)
        )
    ).all()
    return {
        question_revision.id: question_revision
        for question_revision in question_revisions
        if question_revision.id is not None
    }


def build_question_set_publics(
    *,
    test_id: int,
    test_questions: list[TestQuestion],
    question_revisions_map: dict[int, QuestionRevision],
    question_sets: list[QuestionSet],
) -> list[QuestionSetPublic] | None:
    if not question_sets:
        return None

    grouped_question_links: dict[int, list[TestQuestion]] = defaultdict(list)
    for test_question in test_questions:
        if test_question.question_set_id is not None:
            grouped_question_links[test_question.question_set_id].append(test_question)

    return [
        QuestionSetPublic(
            id=question_set.id,
            created_date=question_set.created_date,
            modified_date=question_set.modified_date,
            test_id=test_id,
            title=question_set.title,
            description=question_set.description,
            max_questions_allowed_to_attempt=question_set.max_questions_allowed_to_attempt,
            display_order=question_set.display_order,
            marking_scheme=question_set.marking_scheme,
            question_revisions=[
                question_revisions_map[test_question.question_revision_id]
                for test_question in grouped_question_links.get(
                    question_set.id or -1, []
                )
                if test_question.question_revision_id in question_revisions_map
            ],
        )
        for question_set in question_sets
    ]


def build_question_set_summary_publics(
    *,
    test_questions: list[TestQuestion],
    question_sets: list[QuestionSet],
) -> list[QuestionSetSummaryPublic] | None:
    if not question_sets:
        return None

    grouped_question_links: dict[int, list[TestQuestion]] = defaultdict(list)
    for test_question in test_questions:
        if test_question.question_set_id is not None:
            grouped_question_links[test_question.question_set_id].append(test_question)

    return [
        QuestionSetSummaryPublic(
            id=question_set.id,
            title=question_set.title,
            description=question_set.description,
            max_questions_allowed_to_attempt=question_set.max_questions_allowed_to_attempt,
            display_order=question_set.display_order,
            marking_scheme=question_set.marking_scheme,
            question_count=len(grouped_question_links.get(question_set.id or -1, [])),
        )
        for question_set in question_sets
    ]


def get_total_questions(test: Test, explicit_question_count: int) -> int:
    total_questions = (
        test.no_of_random_questions
        if test.random_questions and test.no_of_random_questions
        else explicit_question_count
    )
    if test.random_tag_count:
        total_questions += sum(
            tag_rule.get("count", 0) for tag_rule in test.random_tag_count
        )
    return total_questions


def build_test_public_response(session: SessionDep, test: Test) -> TestPublic:
    test_id = get_persisted_test_id(test)
    tags = session.exec(
        select(Tag).join(TestTag).where(TestTag.test_id == test_id)
    ).all()
    states = session.exec(
        select(State).join(TestState).where(TestState.test_id == test_id)
    ).all()
    districts = session.exec(
        select(District).join(TestDistrict).where(TestDistrict.test_id == test_id)
    ).all()

    test_questions = get_test_question_links(session, test_id)
    question_revision_ids = [
        test_question.question_revision_id for test_question in test_questions
    ]
    question_revisions_map = get_question_revisions_map(session, question_revision_ids)
    question_revisions = [
        question_revisions_map[question_revision_id]
        for question_revision_id in question_revision_ids
        if question_revision_id in question_revisions_map
    ]
    question_sets = get_test_question_sets(session, test_id)

    if question_sets:
        try:
            is_sectioned_test(
                test_questions,
                {
                    question_set.id: question_set
                    for question_set in question_sets
                    if question_set.id is not None
                },
                test_id=test_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    random_tag_public = (
        build_random_tag_public(session, test.random_tag_count)
        if test.random_tag_count
        else None
    )

    return TestPublic(
        **test.model_dump(),
        tags=tags,
        question_revisions=question_revisions,
        question_sets=build_question_set_publics(
            test_id=test_id,
            test_questions=test_questions,
            question_revisions_map=question_revisions_map,
            question_sets=question_sets,
        ),
        states=states,
        districts=districts,
        total_questions=get_total_questions(test, len(question_revisions)),
        random_tag_counts=random_tag_public,
    )


def validate_question_set_payload(
    question_sets: Sequence[QuestionSetCreate | QuestionSetUpdate] | None,
) -> list[QuestionSetCreate | QuestionSetUpdate]:
    if not question_sets:
        return []

    seen_question_revision_ids: set[int] = set()
    seen_display_orders: set[int] = set()

    for question_set in question_sets:
        question_revision_ids = question_set.question_revision_ids or []
        if not question_revision_ids:
            raise HTTPException(
                status_code=400,
                detail="Each question set must include at least one question revision.",
            )
        if len(question_revision_ids) != len(set(question_revision_ids)):
            raise HTTPException(
                status_code=400,
                detail="Question revisions cannot be duplicated within a question set.",
            )
        if question_set.display_order in seen_display_orders:
            raise HTTPException(
                status_code=400,
                detail="Question set display_order values must be unique within a test.",
            )
        if question_set.max_questions_allowed_to_attempt > len(question_revision_ids):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Question set max_questions_allowed_to_attempt cannot exceed "
                    "the number of questions in that set."
                ),
            )
        duplicate_question_ids = seen_question_revision_ids.intersection(
            question_revision_ids
        )
        if duplicate_question_ids:
            raise HTTPException(
                status_code=400,
                detail="Question revisions cannot be duplicated across question sets.",
            )
        seen_display_orders.add(question_set.display_order)
        seen_question_revision_ids.update(question_revision_ids)

    return list(question_sets)


def validate_test_membership_payload(
    session: SessionDep,
    *,
    question_revision_ids: list[int],
    question_sets: Sequence[QuestionSetCreate | QuestionSetUpdate] | None,
    random_tag_count: list[TagRandomCreate] | None,
) -> tuple[list[int], list[QuestionSetCreate | QuestionSetUpdate]]:
    validated_question_sets = validate_question_set_payload(question_sets)

    if validated_question_sets and random_tag_count:
        raise HTTPException(
            status_code=400,
            detail="Question-set tests do not support tag-based random question selection in this pass.",
        )

    if question_revision_ids and len(question_revision_ids) != len(
        set(question_revision_ids)
    ):
        raise HTTPException(
            status_code=400,
            detail="Question revisions cannot be duplicated within a test.",
        )

    expected_revision_ids = (
        question_revision_ids
        if not validated_question_sets
        else [
            question_revision_id
            for question_set in validated_question_sets
            for question_revision_id in question_set.question_revision_ids
        ]
    )

    if expected_revision_ids:
        question_revisions = session.exec(
            select(QuestionRevision).where(
                col(QuestionRevision.id).in_(expected_revision_ids)
            )
        ).all()
        question_revisions_by_id = {
            question_revision.id: question_revision
            for question_revision in question_revisions
            if question_revision.id is not None
        }
        missing_revision_ids = set(expected_revision_ids) - set(
            question_revisions_by_id
        )
        if missing_revision_ids:
            raise HTTPException(
                status_code=404,
                detail="One or more question revisions were not found.",
            )
        for question_set in validated_question_sets:
            mandatory_question_count = sum(
                1
                for question_revision_id in question_set.question_revision_ids
                if question_revisions_by_id[question_revision_id].is_mandatory
            )
            if mandatory_question_count > question_set.max_questions_allowed_to_attempt:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Question set max_questions_allowed_to_attempt cannot be less "
                        "than the number of mandatory questions in that set."
                    ),
                )

    return question_revision_ids, validated_question_sets


def validate_random_question_config(
    *,
    random_questions: bool,
    no_of_random_questions: int | None,
    question_revision_ids: Sequence[int],
    question_sets_present: bool,
) -> None:
    if not random_questions:
        return

    if question_sets_present:
        raise HTTPException(
            status_code=400,
            detail=(
                "Question-set tests do not support random question selection in "
                "this pass."
            ),
        )

    if no_of_random_questions is None or no_of_random_questions < 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "No. of random questions must be provided if random questions "
                "are enabled."
            ),
        )

    total_questions = len(question_revision_ids)
    if no_of_random_questions > total_questions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No. of random questions ({no_of_random_questions}) "
                f"cannot be greater than total questions added ({total_questions})"
            ),
        )


def replace_test_question_membership(
    session: SessionDep,
    *,
    test: Test,
    question_revision_ids: list[int],
    question_sets: list[QuestionSetCreate | QuestionSetUpdate],
) -> None:
    test_id = get_persisted_test_id(test)
    existing_candidate_test_id = session.exec(
        select(CandidateTest.id).where(CandidateTest.test_id == test_id)
    ).first()
    if existing_candidate_test_id is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot update test membership after candidate tests have been created."
            ),
        )

    for test_question in get_test_question_links(session, test_id):
        session.delete(test_question)

    for question_set in get_test_question_sets(session, test_id):
        session.delete(question_set)

    session.flush()

    if question_sets:
        for question_set_payload in sorted(
            question_sets, key=lambda question_set: question_set.display_order
        ):
            question_set = QuestionSet(
                test_id=test_id,
                title=question_set_payload.title,
                description=question_set_payload.description,
                max_questions_allowed_to_attempt=question_set_payload.max_questions_allowed_to_attempt,
                display_order=question_set_payload.display_order,
                marking_scheme=question_set_payload.marking_scheme,
            )
            session.add(question_set)
            session.flush()
            for question_revision_id in question_set_payload.question_revision_ids:
                session.add(
                    TestQuestion(
                        test_id=test_id,
                        question_revision_id=question_revision_id,
                        question_set_id=question_set.id,
                    )
                )
        session.flush()
        return

    for question_revision_id in question_revision_ids:
        session.add(
            TestQuestion(
                test_id=test_id,
                question_revision_id=question_revision_id,
            )
        )
    session.flush()


def transform_tests_to_public(
    session: SessionDep, tests: list[Test] | Any
) -> list[TestPublic]:
    """
    Transform a list of Test objects to TestPublic objects with all nested relationships.
    """
    test_list: list[Test] = list(tests) if not isinstance(tests, list) else tests
    return [build_test_public_response(session, test) for test in test_list]


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


def resolve_test_by_uuid(session: SessionDep, test_uuid: str) -> Test | None:
    """
    Look up a Test by a UUID that may be either a TestLink.uuid or the
    legacy Test.link value. TestLink takes precedence.
    """
    test_link = session.exec(select(TestLink).where(TestLink.uuid == test_uuid)).first()
    if test_link:
        return session.get(Test, test_link.test_id)
    return None


# Public endpoint to get basic test information (for landing page)
@router.get("/public/{test_uuid}", response_model=TestPublicLimited)
def get_public_test_info(test_uuid: str, session: SessionDep) -> TestPublicLimited:
    """
    Get public information for a test using its UUID link.
    This endpoint is for the test landing page before starting the test.
    No authentication required.
    """
    test = resolve_test_by_uuid(session, test_uuid)
    if not test or test.is_active is False:
        raise HTTPException(status_code=404, detail="Test not found or not active")
    current_time = get_current_time()
    if test.end_time is not None and test.end_time < current_time:
        raise HTTPException(status_code=400, detail="Test has already ended")

    test_id = get_persisted_test_id(test)
    test_questions = get_test_question_links(session, test_id)
    question_sets = get_test_question_sets(session, test_id)
    total_questions = get_total_questions(test, len(test_questions))

    # Include form structure if form_id is set
    form_public: FormPublic | None = None
    if test.form_id:
        form = session.exec(
            select(Form)
            .options(selectinload(Form.fields))  # type: ignore[arg-type]
            .where(Form.id == test.form_id)
        ).first()
        if form:
            fields_public = [
                FormFieldPublic(**field.model_dump())
                for field in sorted(form.fields or [], key=lambda f: f.order)
            ]
            form_public = FormPublic(
                **form.model_dump(exclude={"fields"}),
                fields=fields_public,
            )

    # Apply org-settings runtime overrides so a feature the admin has since
    # disabled (e.g. mark_for_review) is reflected in the landing payload even
    # when the test row was created before the admin's change.
    test_data = get_effective_test_flags(session, test)
    nomenclature = resolve_nomenclature_for_test(session, test)

    return TestPublicLimited(
        **test_data,
        total_questions=total_questions,
        question_sets=build_question_set_summary_publics(
            test_questions=test_questions,
            question_sets=question_sets,
        ),
        form=form_public,
        nomenclature=nomenclature,
        link=test_uuid,
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
    question_revision_ids, question_sets = validate_test_membership_payload(
        session,
        question_revision_ids=test_create.question_revision_ids or [],
        question_sets=test_create.question_sets,
        random_tag_count=test_create.random_tag_count,
    )
    test_data = test_create.model_dump(
        exclude={
            "tag_ids",
            "question_revision_ids",
            "question_sets",
            "state_ids",
            "district_ids",
        }
    )
    test_data["created_by_id"] = current_user.id
    test_data["organization_id"] = current_user.organization_id

    if current_user.organization_id is not None:
        settings_payload = crud_settings.get_payload(
            session=session, organization_id=current_user.organization_id
        )
        if settings_payload is not None:
            test_data.update(fixed_overrides_for_test(settings_payload))

    validate_test_time_config(
        test_data.get("start_time"),
        test_data.get("end_time"),
        test_data.get("time_limit"),
    )
    test = Test.model_validate(test_data)
    effective_question_revision_ids = (
        question_revision_ids
        if not question_sets
        else [
            question_revision_id
            for question_set in question_sets
            for question_revision_id in question_set.question_revision_ids
        ]
    )
    validate_random_question_config(
        random_questions=test.random_questions,
        no_of_random_questions=test.no_of_random_questions,
        question_revision_ids=effective_question_revision_ids,
        question_sets_present=bool(question_sets),
    )

    session.add(test)
    session.flush()

    if test_create.tag_ids:
        tag_ids = test_create.tag_ids
        tag_links = [TestTag(test_id=test.id, tag_id=tag_id) for tag_id in tag_ids]
        session.add_all(tag_links)

    replace_test_question_membership(
        session,
        test=test,
        question_revision_ids=question_revision_ids,
        question_sets=question_sets,
    )

    if test_create.state_ids:
        state_ids = test_create.state_ids
        state_links = [
            TestState(test_id=test.id, state_id=state_id) for state_id in state_ids
        ]
        session.add_all(state_links)
    if test_create.district_ids:
        district_ids = test_create.district_ids
        district_links = [
            TestDistrict(test_id=test.id, district_id=district_id)
            for district_id in district_ids
        ]
        session.add_all(district_links)

    session.commit()
    session.refresh(test)

    return build_test_public_response(session, test)


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
            # tests with no district AND no state assigned
            no_location_assigned = ~exists(
                select(TestDistrict.test_id).where(TestDistrict.test_id == Test.id)
            ) & ~exists(select(TestState.test_id).where(TestState.test_id == Test.id))

            # tests assigned to current users district
            district_subquery = (
                select(TestDistrict.test_id)
                .where(col(TestDistrict.district_id).in_(current_user_district_ids))
                .distinct()
            )

            # show unassigned tests OR tests matching users district
            query = query.where(
                or_(
                    no_location_assigned,
                    col(Test.id).in_(district_subquery),
                )
            )
        else:
            current_user_state_ids = (
                [state.id for state in current_user.states]
                if current_user.states
                else []
            )
            if current_user_state_ids:
                # tests with no state assigned
                no_state_assigned = ~exists(
                    select(TestState.test_id).where(TestState.test_id == Test.id)
                )

                # tests assigned to current users state
                state_subquery = (
                    select(TestState.test_id)
                    .where(col(TestState.state_id).in_(current_user_state_ids))
                    .distinct()
                )

                # show unassigned tests OR tests matching users state
                query = query.where(
                    or_(
                        no_state_assigned,
                        col(Test.id).in_(state_subquery),
                    )
                )

        # if no district or state assigned, show all tests (no filter applied)

    # apply default sorting if no sorting was specified
    sorting_with_default = sorting.apply_default_if_none(
        "modified_date", SortOrder.DESC
    )
    query = sorting_with_default.apply_to_query(query, TestSortConfig)

    # apply filters only if they're provided
    if is_active is not None:
        query = query.where(Test.is_active == is_active)

    if name is not None:
        query = query.where(
            func.lower(Test.name).contains(name.strip().lower(), autoescape=True)
        )

    if description is not None:
        query = query.where(
            func.lower(Test.description).contains(
                description.strip().lower(), autoescape=True
            )
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
    "/{test_id}/link",
    response_model=TestLinkPublic,
    dependencies=[Depends(permission_dependency("read_test"))],
)
def get_or_create_test_link(
    test_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TestLinkPublic:
    """
    Return the unique shareable link UUID for the current admin and this test.
    If none exists yet, one is generated and persisted. Idempotent.
    """
    test = session.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if test.is_template:
        raise HTTPException(
            status_code=400, detail="Templates do not have shareable links."
        )
    assert current_user.id is not None
    existing = session.exec(
        select(TestLink).where(
            TestLink.test_id == test_id, TestLink.created_by_id == current_user.id
        )
    ).first()
    if existing:
        return TestLinkPublic.model_validate(existing)
    new_link = TestLink(
        uuid=str(uuid.uuid4()), test_id=test_id, created_by_id=current_user.id
    )
    session.add(new_link)
    session.commit()
    session.refresh(new_link)
    assert new_link.id is not None
    return TestLinkPublic.model_validate(new_link)


@router.get(
    "/{test_id}",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("read_test"))],
)
def get_test_by_id(
    test_id: int, session: SessionDep, current_user: CurrentUser
) -> TestPublic:
    test = session.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test is not available")

    # check location based access for state/district admins
    role = session.get(Role, current_user.role_id)
    if role and role.name in (state_admin.name, test_admin.name):
        check_test_permission(session, current_user, test)

    return build_test_public_response(session, test)


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
    membership_fields = {"question_revision_ids", "question_sets"}
    membership_update_requested = bool(
        membership_fields.intersection(test_update.model_fields_set)
    )
    if membership_update_requested:
        question_revision_ids, question_sets = validate_test_membership_payload(
            session,
            question_revision_ids=test_update.question_revision_ids or [],
            question_sets=test_update.question_sets,
            random_tag_count=test_update.random_tag_count,
        )
    else:
        question_revision_ids = []
        question_sets = []
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
    existing_test_questions = get_test_question_links(session, test_id)
    existing_question_sets = get_test_question_sets(session, test_id)
    effective_question_revision_ids = (
        [
            test_question.question_revision_id
            for test_question in existing_test_questions
        ]
        if not membership_update_requested
        else (
            question_revision_ids
            if not question_sets
            else [
                question_revision_id
                for question_set in question_sets
                for question_revision_id in question_set.question_revision_ids
            ]
        )
    )
    validate_random_question_config(
        random_questions=(
            test_update.random_questions
            if "random_questions" in test_update.model_fields_set
            else test.random_questions
        ),
        no_of_random_questions=(
            test_update.no_of_random_questions
            if "no_of_random_questions" in test_update.model_fields_set
            else test.no_of_random_questions
        ),
        question_revision_ids=effective_question_revision_ids,
        question_sets_present=(
            bool(existing_question_sets)
            if not membership_update_requested
            else bool(question_sets)
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

    if membership_update_requested:
        replace_test_question_membership(
            session,
            test=test,
            question_revision_ids=question_revision_ids,
            question_sets=question_sets,
        )

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
    test_data = test_update.model_dump(
        exclude_unset=True,
        exclude={
            "tag_ids",
            "question_revision_ids",
            "question_sets",
            "state_ids",
            "district_ids",
        },
    )
    if test.organization_id is not None:
        settings_payload = crud_settings.get_payload(
            session=session, organization_id=test.organization_id
        )
        if settings_payload is not None:
            test_data.update(fixed_overrides_for_test(settings_payload))
    test.sqlmodel_update(test_data)
    session.add(test)
    session.commit()
    session.refresh(test)

    return build_test_public_response(session, test)


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

    return build_test_public_response(session, test)


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
    admin_location_ids: set[int] | None = None
    admin_location_level: Literal["state", "district"] | None = None

    if role and role.name in (state_admin.name, test_admin.name):
        admin_location_level, admin_location_ids = get_current_user_location_ids(
            current_user
        )
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
    test = resolve_test_by_uuid(session, test_uuid)
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
    original_id = get_persisted_test_id(original)

    test_data = original.model_dump(exclude={"id", "created_date", "modified_date"})
    test_data["name"] = f"Copy of {original.name}"
    test_data["created_by_id"] = current_user.id
    test_data["organization_id"] = current_user.organization_id

    new_test = Test.model_validate(test_data)
    session.add(new_test)
    session.flush()

    tag_links = session.exec(
        select(TestTag).where(TestTag.test_id == original_id)
    ).all()
    for tag_link in tag_links:
        session.add(TestTag(test_id=new_test.id, tag_id=tag_link.tag_id))

    original_question_sets = get_test_question_sets(session, original_id)
    question_set_id_map: dict[int, int] = {}
    for original_question_set in original_question_sets:
        new_question_set = QuestionSet(
            test_id=new_test.id,
            title=original_question_set.title,
            description=original_question_set.description,
            max_questions_allowed_to_attempt=original_question_set.max_questions_allowed_to_attempt,
            display_order=original_question_set.display_order,
            marking_scheme=original_question_set.marking_scheme,
        )
        session.add(new_question_set)
        session.flush()
        if original_question_set.id is not None and new_question_set.id is not None:
            question_set_id_map[original_question_set.id] = new_question_set.id

    question_links = session.exec(
        select(TestQuestion)
        .where(TestQuestion.test_id == original_id)
        .order_by(col(TestQuestion.id))
    ).all()
    for ql in question_links:
        session.add(
            TestQuestion(
                test_id=new_test.id,
                question_revision_id=ql.question_revision_id,
                question_set_id=(
                    question_set_id_map.get(ql.question_set_id)
                    if ql.question_set_id is not None
                    else None
                ),
            )
        )
    state_links = session.exec(
        select(TestState).where(TestState.test_id == original.id)
    ).all()
    for sl in state_links:
        session.add(TestState(test_id=new_test.id, state_id=sl.state_id))
    district_links = session.exec(
        select(TestDistrict).where(TestDistrict.test_id == original.id)
    ).all()
    for dl in district_links:
        session.add(TestDistrict(test_id=new_test.id, district_id=dl.district_id))
    session.commit()
    session.refresh(new_test)

    return build_test_public_response(session, new_test)
