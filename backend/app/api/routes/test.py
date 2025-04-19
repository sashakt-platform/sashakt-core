from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import asc, desc, select

from app.api.deps import SessionDep, permission_dependency
from app.models import (
    Message,
    QuestionRevision,
    Test,
    TestCreate,
    TestPublic,
    TestQuestion,
    TestState,
    TestTag,
    TestUpdate,
)
from app.models.test import MarksLevelEnum

router = APIRouter(prefix="/test", tags=["Test"])


# Create a Test
@router.post(
    "/",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("create_test"))],
)
def create_test(
    test_create: TestCreate,
    session: SessionDep,
) -> TestPublic:
    test_data = test_create.model_dump(
        exclude={"tags", "question_revision_ids", "states"}
    )
    test = Test.model_validate(test_data)
    session.add(test)
    session.commit()
    session.refresh(test)

    if test_create.tags:
        tag_ids = test_create.tags
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

    if test_create.states:
        state_ids = test_create.states
        state_links = [
            TestState(test_id=test.id, state_id=state_id) for state_id in state_ids
        ]
        session.add_all(state_links)
        session.commit()

    stored_revision_ids = session.exec(
        select(TestQuestion.question_revision_id).where(TestQuestion.test_id == test.id)
    ).all()

    stored_tag_ids = session.exec(
        select(TestTag.tag_id).where(TestTag.test_id == test.id)
    )
    stored_state_ids = session.exec(
        select(TestState.state_id).where(TestState.test_id == test.id)
    )

    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        question_revision_ids=stored_revision_ids,
        states=stored_state_ids,
    )


# Get All Tests
@router.get(
    "/",
    response_model=list[TestPublic],
    dependencies=[Depends(permission_dependency("read_test"))],
)
def get_test(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
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
    no_of_questions: int | None = None,
    no_of_questions_gte: int | None = Query(None),
    no_of_questions_lte: int | None = None,
    question_pagination: int | None = None,
    is_template: bool | None = None,
    created_by: list[int] | None = Query(None),
    is_active: bool | None = None,
    is_deleted: bool | None = False,  # Default to showing non-deleted questions
    sort: Annotated[str, Query(description="Field to sort by")] = "created_date",
    order: Annotated[Literal["asc", "desc"], Query(description="Sort order")] = "asc",
) -> Sequence[TestPublic]:
    query = select(Test)

    sort_column = getattr(Test, sort, None)
    if sort_column is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort field: {sort}",
        )

    sort_asc = asc(sort_column) if order == "asc" else desc(sort_column)

    query = query.order_by(sort_asc)

    # Apply filters only if they're provided
    if is_deleted is not None:
        query = query.where(Test.is_deleted == is_deleted)

    if is_active is not None:
        query = query.where(Test.is_active == is_active)

    if name is not None:
        query = query.where(Test.name.like(f"%{name}%"))

    if description is not None:
        query = query.where(Test.description.like(f"%{description}%"))

    if completion_message is not None:
        query = query.where(Test.completion_message.like(f"%{completion_message}%"))

    if start_instructions is not None:
        query = query.where(Test.start_instructions.like(f"%{start_instructions}%"))

    if start_time_gte is not None:
        query = query.where(Test.start_time >= start_time_gte)
    if start_time_lte is not None:
        query = query.where(Test.start_time <= start_time_lte)

    if end_time_gte is not None:
        query = query.where(Test.end_time >= end_time_gte)
    if end_time_lte is not None:
        query = query.where(Test.end_time <= end_time_lte)

    if time_limit_gte is not None:
        query = query.where(Test.time_limit >= time_limit_gte)
    if time_limit_lte is not None:
        query = query.where(Test.time_limit <= time_limit_lte)

    if marks_level is not None:
        query = query.where(Test.marks_level == marks_level)

    if no_of_attempts is not None:
        query = query.where(Test.no_of_attempts == no_of_attempts)

    if no_of_attempts_gte is not None:
        query = query.where(Test.no_of_attempts >= no_of_attempts_gte)
    if no_of_attempts_lte is not None:
        query = query.where(Test.no_of_attempts <= no_of_attempts_lte)

    if shuffle is not None:
        query = query.where(Test.shuffle == shuffle)

    if random_questions is not None:
        query = query.where(Test.random_questions == random_questions)

    if no_of_questions is not None:
        query = query.where(Test.no_of_questions == no_of_questions)
    if no_of_questions_gte is not None:
        query = query.where(Test.no_of_questions >= no_of_questions_gte)
    if no_of_questions_lte is not None:
        query = query.where(Test.no_of_questions <= no_of_questions_lte)

    if question_pagination is not None:
        query = query.where(Test.question_pagination == question_pagination)

    if is_template is not None:
        query = query.where(Test.is_template == is_template)

    if created_by is not None:
        query = query.where(Test.created_by_id.in_(created_by))

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query and get all questions
    tests = session.exec(query).all()

    test_public = []

    for test in tests:
        stored_tag_ids = session.exec(
            select(TestTag.tag_id).where(TestTag.test_id == test.id)
        )

        # Get question_revision_ids instead of question_ids
        stored_revision_ids = session.exec(
            select(TestQuestion.question_revision_id).where(
                TestQuestion.test_id == test.id
            )
        )

        stored_state_ids = session.exec(
            select(TestState.state_id).where(TestState.test_id == test.id)
        )

        test_public.append(
            TestPublic(
                **test.model_dump(),
                tags=stored_tag_ids,
                question_revision_ids=stored_revision_ids,
                states=stored_state_ids,
            )
        )

    return test_public


@router.get(
    "/{test_id}",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("read_test"))],
)
def get_test_by_id(test_id: int, session: SessionDep) -> TestPublic:
    test = session.get(Test, test_id)
    if not test or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")

    stored_tag_ids = session.exec(
        select(TestTag.tag_id).where(TestTag.test_id == test_id)
    )
    stored_revision_ids = session.exec(
        select(TestQuestion.question_revision_id).where(TestQuestion.test_id == test_id)
    )
    stored_state_ids = session.exec(
        select(TestState.state_id).where(TestState.test_id == test_id)
    )
    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        question_revision_ids=stored_revision_ids,
        states=stored_state_ids,
    )


@router.put(
    "/{test_id}",
    response_model=TestPublic,
    dependencies=[Depends(permission_dependency("update_test"))],
)
def update_test(
    test_id: int, test_update: TestUpdate, session: SessionDep
) -> TestPublic:
    test = session.get(Test, test_id)
    print("test-->", test)
    if not test or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")

    # Updating Tags
    tags_remove = [
        tag.id for tag in (test.tags or []) if tag.id not in (test_update.tags or [])
    ]
    tags_add = [
        tag
        for tag in (test_update.tags or [])
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

    stored_tag_ids = session.exec(
        select(TestTag.tag_id).where(TestTag.test_id == test.id)
    )

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

    # Get updated question_revision_ids
    stored_revision_ids = session.exec(
        select(TestQuestion.question_revision_id).where(TestQuestion.test_id == test.id)
    )

    # Updating States
    states_remove = [
        state.id
        for state in (test.states or [])
        if state.id not in (test_update.states or [])
    ]
    states_add = [
        state
        for state in (test_update.states or [])
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

    stored_state_ids = session.exec(
        select(TestState.state_id).where(TestState.test_id == test.id)
    )

    test_data = test_update.model_dump(exclude_unset=True)
    test.sqlmodel_update(test_data)
    session.add(test)
    session.commit()
    session.refresh(test)

    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        question_revision_ids=stored_revision_ids,
        states=stored_state_ids,
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

    stored_tag_ids = session.exec(
        select(TestTag.tag_id).where(TestTag.test_id == test_id)
    )

    # Get question_revision_ids instead of question_ids
    stored_revision_ids = session.exec(
        select(TestQuestion.question_revision_id).where(TestQuestion.test_id == test_id)
    )

    stored_state_ids = session.exec(
        select(TestState.state_id).where(TestState.test_id == test_id)
    )

    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        question_revision_ids=stored_revision_ids,
        states=stored_state_ids,
    )


@router.delete(
    "/{test_id}",
    dependencies=[Depends(permission_dependency("delete_test"))],
)
def delete_test(test_id: int, session: SessionDep) -> Message:
    test = session.get(Test, test_id)
    if not test or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")

    test.is_deleted = True
    session.add(test)
    session.commit()
    session.refresh(test)

    return Message(message="Test deleted successfully")
