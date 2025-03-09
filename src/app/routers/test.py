from fastapi import APIRouter, Body, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.test import (
    Test,
    TestCreate,
    TestPublic,
    TestQuestionStaticLink,
    TestTagLink,
)

router = APIRouter(prefix="/test", tags=["Test"])


# Create a Test
@router.post("/", response_model=TestPublic)
def create_test(
    test_create: TestCreate,
    tag_ids: list[int] = Body(default=[], description="IDs off associated Tags"),
    question_ids: list[int] = Body(
        default=[], description="IDs off associated Question"
    ),
    session: Session = Depends(get_session),
):
    test = Test.model_validate(test_create)
    session.add(test)
    session.commit()
    session.refresh(test)

    tag_links = [TestTagLink(test_id=test.id, tag_id=tag_id) for tag_id in tag_ids]
    session.add_all(tag_links)
    session.commit()

    stored_tag_ids = session.exec(
        select(TestTagLink.tag_id).where(TestTagLink.test_id == test.id)
    )

    question_links = [
        TestQuestionStaticLink(test_id=test.id, question_id=question_id)
        for question_id in question_ids
    ]
    session.add_all(question_links)
    session.commit()

    stored_question_ids = session.exec(
        select(TestQuestionStaticLink.question_id).where(
            TestQuestionStaticLink.test_id == test.id
        )
    )

    return TestPublic(
        **test.model_dump(),
        tags=stored_tag_ids,
        test_question_static=stored_question_ids,
    )


# Get All Tests
@router.get("/", response_model=list[TestPublic])
def get_test(session: Session = Depends(get_session)):
    states = session.exec(select(Test)).all()
    return states
