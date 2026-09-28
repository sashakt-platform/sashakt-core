from sqlmodel import Session

from app.models import QuestionSet, Test, TestQuestion
from app.models.user import User
from app.services.data_sync import DataSyncService
from app.tests.utils.candidate import create_test_record
from app.tests.utils.organization import create_random_organization
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.user import create_random_user


def _org_user(db: Session) -> User:
    org = create_random_organization(db)
    return create_random_user(db, organization_id=org.id)


def _sectioned_test(
    db: Session, user: User, title: str = "Chemistry"
) -> tuple[Test, QuestionSet]:
    """A test with one question set holding one question."""
    test = create_test_record(db, user_id=user.id, organization_id=user.organization_id)
    revision = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    question_set = QuestionSet(
        test_id=test.id,
        title=title,
        max_questions_allowed_to_attempt=1,
        display_order=1,
        marking_scheme={"correct": 4, "wrong": -2, "skipped": 0},
    )
    db.add(question_set)
    db.commit()
    db.refresh(question_set)

    db.add(
        TestQuestion(
            test_id=test.id,
            question_set_id=question_set.id,
            question_revision_id=revision.id,
        )
    )
    db.commit()
    return test, question_set


def test_question_sets_are_exported(db: Session) -> None:
    user = _org_user(db)
    _, question_set = _sectioned_test(db, user)

    service = DataSyncService()
    rows = service._extract_question_sets_data(db, user.organization_id, False)

    row = next(r for r in rows if r["id"] == question_set.id)
    assert row["title"] == "Chemistry"
    assert row["display_order"] == 1
    assert row["max_questions_allowed_to_attempt"] == 1
    # the set-level scheme is the reason this table matters: marking resolves
    # question -> set -> test, so without it a section scores wrong downstream
    assert row["marking_scheme"] == {"correct": 4, "wrong": -2, "skipped": 0}
    assert row["organization_id"] == user.organization_id


def test_test_questions_carry_their_question_set(db: Session) -> None:
    user = _org_user(db)
    test, question_set = _sectioned_test(db, user)

    service = DataSyncService()
    rows = service._extract_test_questions_data(db, user.organization_id, False)

    links = [r for r in rows if r["test_id"] == test.id]
    assert links, "expected the test's question link to be exported"
    assert links[0]["question_set_id"] == question_set.id


def test_question_sets_are_scoped_to_the_organization(db: Session) -> None:
    user = _org_user(db)
    _, mine = _sectioned_test(db, user, title="Mine")

    other = _org_user(db)
    _, theirs = _sectioned_test(db, other, title="Theirs")

    service = DataSyncService()
    rows = service._extract_question_sets_data(db, user.organization_id, False)

    ids = {r["id"] for r in rows}
    assert mine.id in ids
    assert theirs.id not in ids


def test_question_sets_are_synced_before_the_links_that_reference_them(
    db: Session,
) -> None:
    # A question set row must exist before a test_question points at it.
    user = _org_user(db)
    _sectioned_test(db, user)

    service = DataSyncService()
    data = service._extract_organization_data(user.organization_id, incremental=False)

    order = list(data.keys())
    assert order.index("question_sets") < order.index("test_questions")
