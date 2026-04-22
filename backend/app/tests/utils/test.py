import uuid

from sqlmodel import Session

from app.models.test import TestLink


def get_test_link(
    session: Session, test_id: int | None, admin_id: int | None
) -> TestLink:
    assert test_id, admin_id is not None
    test_link = TestLink(
        test_id=test_id,
        created_by_id=admin_id,
        uuid=str(uuid.uuid4()),
    )
    session.add(test_link)
    session.commit()
    session.refresh(test_link)
    return test_link
