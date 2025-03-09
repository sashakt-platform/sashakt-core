from fastapi import APIRouter, Body, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.test import Test, TestCreate, TestPublic, TestTagLink

router = APIRouter(prefix="/test", tags=["Test"])


# Create a Test
@router.post("/", response_model=TestPublic)
def create_test(
    test_create: TestCreate,
    tag_ids: list[int] = Body(default=[]),
    session: Session = Depends(get_session),
):
    test = Test.model_validate(test_create)
    print("test-->", test)
    session.add(test)
    session.commit()
    session.refresh(test)

    tag_links = [TestTagLink(test_id=test.id, tag_id=tag_id) for tag_id in tag_ids]
    session.add_all(tag_links)
    session.commit()

    stored_tag_ids = session.exec(
        select(TestTagLink.tag_id).where(TestTagLink.test_id == test.id)
    )

    return TestPublic(**test.model_dump(), tags=stored_tag_ids)
