from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep
from app.models.test import (
    Test,
    TestCreate,
    TestPublic,
    TestQuestionStaticLink,
    TestStateLocationLink,
    TestTagLink,
    TestUpdate,
)

router = APIRouter(prefix="/test", tags=["Test"])


# Create a Test
@router.post("/", response_model=TestPublic)
def create_test(
    test_create: TestCreate,
    session: SessionDep,
):
    test_data = test_create.model_dump(
        exclude={"tags", "test_question_static", "states"}
    )
    test = Test.model_validate(test_data)
    session.add(test)
    session.commit()
    session.refresh(test)

    if test_create.tags:
        tag_ids = test_create.tags
        tag_links = [TestTagLink(test_id=test.id, tag_id=tag_id) for tag_id in tag_ids]
        session.add_all(tag_links)
        session.commit()

    if test_create.test_question_static:
        question_ids = test_create.test_question_static
        question_links = [
            TestQuestionStaticLink(test_id=test.id, question_id=question_id)
            for question_id in question_ids
        ]
        session.add_all(question_links)
        session.commit()

    if test_create.states:
        state_ids = test_create.states
        state_links = [
            TestStateLocationLink(test_id=test.id, state_id=state_id)
            for state_id in state_ids
        ]
        session.add_all(state_links)
        session.commit()

    stored_question_ids = session.exec(
        select(TestQuestionStaticLink.question_id).where(
            TestQuestionStaticLink.test_id == test.id
        )
    )

    stored_tag_ids = session.exec(
        select(TestTagLink.tag_id).where(TestTagLink.test_id == test.id)
    )

    stored_state_ids = session.exec(
        select(TestStateLocationLink.state_id).where(
            TestStateLocationLink.test_id == test.id
        )
    )

    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        test_question_static=stored_question_ids,
        states=stored_state_ids,
    )


# Get All Tests
@router.get("/", response_model=list[TestPublic])
def get_test(session: SessionDep):
    tests = session.exec(
        select(Test)
        .where(Test.is_active is not False)
        .where(Test.is_deleted is not True)
    ).all()

    test_public = []
    for test in tests:
        stored_tag_ids = session.exec(
            select(TestTagLink.tag_id).where(TestTagLink.test_id == test.id)
        )
        stored_question_ids = session.exec(
            select(TestQuestionStaticLink.question_id).where(
                TestQuestionStaticLink.test_id == test.id
            )
        )
        stored_state_ids = session.exec(
            select(TestStateLocationLink.state_id).where(
                TestStateLocationLink.test_id == test.id
            )
        )
        test_public.append(
            TestPublic(
                **test.model_dump(),
                tags=stored_tag_ids,
                test_question_static=stored_question_ids,
                states=stored_state_ids,
            )
        )

        return test_public


@router.get("/{test_id}", response_model=TestPublic)
def get_test_by_id(test_id: int, session: SessionDep):
    test = session.get(Test, test_id)
    if not test or test.is_active is False or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")

    stored_tag_ids = session.exec(
        select(TestTagLink.tag_id).where(TestTagLink.test_id == test_id)
    )
    stored_question_ids = session.exec(
        select(TestQuestionStaticLink.question_id).where(
            TestQuestionStaticLink.test_id == test_id
        )
    )
    stored_state_ids = session.exec(
        select(TestStateLocationLink.state_id).where(
            TestStateLocationLink.test_id == test_id
        )
    )
    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        test_question_static=stored_question_ids,
        states=stored_state_ids,
    )


@router.put("/{test_id}", response_model=TestPublic)
def update_test(test_id: int, test_update: TestUpdate, session: SessionDep):
    test = session.get(Test, test_id)
    print("test-->", test)

    if not test or test.is_active is False or test.is_deleted is True:
        raise HTTPException(status_code=404, detail="Test is not available")

    # Updating Tags
    tags_remove = [tag.id for tag in test.tags if tag.id not in test_update.tags]
    tags_add = [tag for tag in test_update.tags if tag not in [t.id for t in test.tags]]

    if tags_remove:
        for tag in tags_remove:
            session.delete(
                session.exec(
                    select(TestTagLink).where(
                        TestTagLink.test_id == test.id, TestTagLink.tag_id == tag
                    )
                ).one()
            )
        session.commit()

    if tags_add:
        for tag in tags_add:
            session.add(TestTagLink(test_id=test.id, tag_id=tag))
        session.commit()

    stored_tag_ids = session.exec(
        select(TestTagLink.tag_id).where(TestTagLink.test_id == test.id)
    )

    # Updating Questions
    question_remove = [
        question.id
        for question in test.test_question_static
        if question.id not in test_update.test_question_static
    ]
    question_add = [
        question
        for question in test_update.test_question_static
        if question not in [q.id for q in test.test_question_static]
    ]

    if question_remove:
        for question in question_remove:
            session.delete(
                session.exec(
                    select(TestQuestionStaticLink).where(
                        TestQuestionStaticLink.test_id == test.id,
                        TestQuestionStaticLink.question_id == question,
                    )
                ).one()
            )
        session.commit()

    if question_add:
        for question in question_add:
            session.add(TestQuestionStaticLink(test_id=test.id, question_id=question))
        session.commit()

    stored_question_ids = session.exec(
        select(TestQuestionStaticLink.question_id).where(
            TestQuestionStaticLink.test_id == test.id
        )
    )

    # Updating States
    states_remove = [
        state.id for state in test.states if state.id not in test_update.states
    ]
    states_add = [
        state
        for state in test_update.states
        if state not in [s.id for s in test.states]
    ]

    if states_remove:
        for state in states_remove:
            session.delete(
                session.exec(
                    select(TestStateLocationLink).where(
                        TestStateLocationLink.test_id == test.id,
                        TestStateLocationLink.state_id == state,
                    )
                ).one()
            )
        session.commit()

    if states_add:
        for state in states_add:
            session.add(TestStateLocationLink(test_id=test.id, state_id=state))
        session.commit()

    stored_state_ids = session.exec(
        select(TestStateLocationLink.state_id).where(
            TestStateLocationLink.test_id == test.id
        )
    )

    test_data = test_update.model_dump(exclude_unset=True)
    test.sqlmodel_update(test_data)
    session.add(test)
    session.commit()
    session.refresh(test)

    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        test_question_static=stored_question_ids,
        states=stored_state_ids,
    )
