"""Seed a freshly-reset database with sample data for manual testing.

Prerequisite: `initial_data.py` has already run (roles, permissions, country/
states/districts, superuser, T4D org all exist).

Idempotent: re-running is a no-op once the sample data is present.

Run inside the backend container:
    python app/populate_sample_data.py
Or via the wrapper from the project root:
    bash scripts/populate-sample-data.sh
"""

import logging
import os
import uuid
from typing import Any

from sqlmodel import Session, select

from app import crud
from app.core.db import engine
from app.crud import organization_settings as crud_organization_settings
from app.models import (
    District,
    Entity,
    EntityType,
    Form,
    FormField,
    FormFieldType,
    Organization,
    Question,
    QuestionRevision,
    QuestionTag,
    Role,
    State,
    Tag,
    TagType,
    Test,
    TestDistrict,
    TestQuestion,
    TestState,
    TestTag,
    User,
    UserCreate,
)
from app.models.test import OMRMode
from app.models.user import UserDistrict, UserState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_ORG_NAME = "Sample Organization"
MARKER_EMAIL = "systemadmin@example.com"
DEFAULT_PASSWORD = os.getenv("SAMPLE_DATA_PASSWORD", "ChangeMe123!")
SAMPLE_STATE_NAME = "Maharashtra"

USERS: list[dict[str, str]] = [
    {
        "role": "system_admin",
        "email": MARKER_EMAIL,
        "full_name": "Sample System Admin",
        "phone": "9000000001",
    },
    {
        "role": "state_admin",
        "email": "stateadmin@example.com",
        "full_name": "Sample State Admin",
        "phone": "9000000002",
    },
    {
        "role": "test_admin",
        "email": "testadmin@example.com",
        "full_name": "Sample Test Admin",
        "phone": "9000000003",
    },
]


def _already_seeded(session: Session) -> bool:
    existing = crud.get_user_by_email(session=session, email=MARKER_EMAIL)
    return existing is not None


def _get_role(session: Session, name: str) -> Role:
    role = session.exec(select(Role).where(Role.name == name)).first()
    if role is None:
        raise RuntimeError(
            f"Role {name!r} not found — run `python app/initial_data.py` first."
        )
    return role


def _get_or_create_organization(session: Session) -> Organization:
    org = session.exec(
        select(Organization).where(Organization.name == SAMPLE_ORG_NAME)
    ).first()
    if org is not None:
        return org
    org = Organization(
        name=SAMPLE_ORG_NAME,
        description="Auto-generated organization for local sample data",
    )
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _create_user(
    session: Session,
    *,
    role_id: int,
    org_id: int,
    email: str,
    full_name: str,
    phone: str,
    created_by_id: int | None,
) -> User:
    user_in = UserCreate(
        email=email,
        password=DEFAULT_PASSWORD,
        full_name=full_name,
        phone=phone,
        role_id=role_id,
        organization_id=org_id,
    )
    return crud.create_user(
        session=session, user_create=user_in, created_by_id=created_by_id
    )


def _assign_user_locations(
    session: Session,
    *,
    user_id: int,
    state_id: int,
    district_ids: list[int] | None = None,
) -> None:
    session.add(UserState(user_id=user_id, state_id=state_id))
    if district_ids:
        for did in district_ids:
            session.add(UserDistrict(user_id=user_id, district_id=did))
    session.commit()


def _create_tags(session: Session, *, org_id: int, created_by_id: int) -> list[Tag]:
    tag_type = TagType(
        name="Subject",
        description="Academic subject",
        organization_id=org_id,
        created_by_id=created_by_id,
    )
    session.add(tag_type)
    session.commit()
    session.refresh(tag_type)

    tags: list[Tag] = []
    for name in ("Math", "Science", "English"):
        tag = Tag(
            name=name,
            description=f"Sample {name} tag",
            tag_type_id=tag_type.id,
            organization_id=org_id,
            created_by_id=created_by_id,
        )
        session.add(tag)
        tags.append(tag)
    session.commit()
    for tag in tags:
        session.refresh(tag)
    return tags


def _create_entities(
    session: Session,
    *,
    org_id: int,
    created_by_id: int,
    state_id: int,
    district_id: int,
) -> EntityType:
    entity_type = EntityType(
        name="School",
        description="Educational institution",
        organization_id=org_id,
        created_by_id=created_by_id,
    )
    session.add(entity_type)
    session.commit()
    session.refresh(entity_type)

    for idx, name in enumerate(("Sample Public School", "Sample High School"), start=1):
        entity = Entity(
            name=name,
            description=f"Sample school #{idx}",
            entity_type_id=entity_type.id,
            state_id=state_id,
            district_id=district_id,
            created_by_id=created_by_id,
        )
        session.add(entity)
    session.commit()
    return entity_type


def _create_form(
    session: Session,
    *,
    org_id: int,
    created_by_id: int,
    entity_type: EntityType,
) -> Form:
    form = Form(
        name="Candidate Profile",
        description="Sample candidate profile form with an entity (school) field",
        organization_id=org_id,
        created_by_id=created_by_id,
    )
    session.add(form)
    session.commit()
    session.refresh(form)

    assert form.id is not None
    assert entity_type.id is not None
    session.add(
        FormField(
            form_id=form.id,
            field_type=FormFieldType.ENTITY,
            label="School",
            name="school",
            placeholder="Select your school",
            help_text="Choose the school you belong to",
            is_required=True,
            order=1,
            entity_type_id=entity_type.id,
        )
    )
    session.commit()
    return form


def _create_question(
    session: Session,
    *,
    org_id: int,
    created_by_id: int,
    tag_ids: list[int],
    question_text: str,
    question_type: str,
    options: list[dict[str, Any]] | None,
    correct_answer: list[int] | int | float | None,
    subjective_answer_limit: int | None = None,
) -> QuestionRevision:
    question = Question(organization_id=org_id)
    session.add(question)
    session.commit()
    session.refresh(question)

    assert question.id is not None

    revision = QuestionRevision(
        question_text=question_text,
        question_type=question_type,
        options=options,
        correct_answer=correct_answer,
        subjective_answer_limit=subjective_answer_limit,
        question_id=question.id,
        created_by_id=created_by_id,
    )
    session.add(revision)
    session.commit()
    session.refresh(revision)

    question.last_revision_id = revision.id
    session.add(question)

    for tid in tag_ids:
        session.add(QuestionTag(question_id=question.id, tag_id=tid))
    session.commit()
    session.refresh(revision)
    return revision


def _create_sample_questions(
    session: Session, *, org_id: int, created_by_id: int, tags: list[Tag]
) -> list[QuestionRevision]:
    tag_by_name = {t.name: t.id for t in tags if t.id is not None}
    math = [tag_by_name["Math"]]
    science = [tag_by_name["Science"]]
    english = [tag_by_name["English"]]

    revisions = [
        _create_question(
            session,
            org_id=org_id,
            created_by_id=created_by_id,
            tag_ids=math,
            question_text="What is 2 + 2?",
            question_type="single-choice",
            options=[
                {"id": 1, "key": "A", "value": "3"},
                {"id": 2, "key": "B", "value": "4"},
                {"id": 3, "key": "C", "value": "5"},
                {"id": 4, "key": "D", "value": "6"},
            ],
            correct_answer=[2],
        ),
        _create_question(
            session,
            org_id=org_id,
            created_by_id=created_by_id,
            tag_ids=math,
            question_text="Which of these are even numbers?",
            question_type="multi-choice",
            options=[
                {"id": 1, "key": "A", "value": "2"},
                {"id": 2, "key": "B", "value": "3"},
                {"id": 3, "key": "C", "value": "4"},
                {"id": 4, "key": "D", "value": "7"},
            ],
            correct_answer=[1, 3],
        ),
        _create_question(
            session,
            org_id=org_id,
            created_by_id=created_by_id,
            tag_ids=science,
            question_text="Which planet is known as the Red Planet?",
            question_type="single-choice",
            options=[
                {"id": 1, "key": "A", "value": "Earth"},
                {"id": 2, "key": "B", "value": "Mars"},
                {"id": 3, "key": "C", "value": "Jupiter"},
                {"id": 4, "key": "D", "value": "Venus"},
            ],
            correct_answer=[2],
        ),
        _create_question(
            session,
            org_id=org_id,
            created_by_id=created_by_id,
            tag_ids=english,
            question_text="Briefly explain the main theme of your favourite book.",
            question_type="subjective",
            options=None,
            correct_answer=None,
            subjective_answer_limit=500,
        ),
        _create_question(
            session,
            org_id=org_id,
            created_by_id=created_by_id,
            tag_ids=math,
            question_text="How many continents are there on Earth?",
            question_type="numerical-integer",
            options=None,
            correct_answer=7,
        ),
        _create_question(
            session,
            org_id=org_id,
            created_by_id=created_by_id,
            tag_ids=math,
            question_text="What is the approximate value of pi to two decimal places?",
            question_type="numerical-decimal",
            options=None,
            correct_answer=3.14,
        ),
    ]
    return revisions


def _create_tests(
    session: Session,
    *,
    org_id: int,
    created_by_id: int,
    revisions: list[QuestionRevision],
    tags: list[Tag],
    state_id: int,
    district_ids: list[int],
    form_id: int,
) -> None:
    tag_ids = [t.id for t in tags if t.id is not None]

    # All toggleable features enabled. Skips flags that require extra config:
    # random_questions (needs no_of_random_questions), is_template (would
    # convert the test into a template).
    feature_flags: dict[str, Any] = {
        "shuffle": True,
        "show_result": True,
        "show_question_palette": True,
        "show_feedback_on_completion": True,
        "show_feedback_immediately": True,
        "bookmark": True,
        "show_marks": True,
        "omr": OMRMode.OPTIONAL,
        "marking_scheme": {"correct": 1, "wrong": 0, "skipped": 0},
        "candidate_profile": True,
        "form_id": form_id,
    }

    test1 = Test(
        name="Sample Mixed Test",
        description="Covers math, science and English",
        created_by_id=created_by_id,
        organization_id=org_id,
        time_limit=30,
        link=str(uuid.uuid4()),
        **feature_flags,
    )
    session.add(test1)
    session.commit()
    session.refresh(test1)
    assert test1.id is not None
    for rev in revisions:
        assert rev.id is not None
        session.add(TestQuestion(test_id=test1.id, question_revision_id=rev.id))
    for tid in tag_ids:
        session.add(TestTag(test_id=test1.id, tag_id=tid))
    session.add(TestState(test_id=test1.id, state_id=state_id))
    for did in district_ids:
        session.add(TestDistrict(test_id=test1.id, district_id=did))
    session.commit()

    math_revisions = [
        r
        for r in revisions
        if r.question_type
        in (
            "single-choice",
            "multi-choice",
            "numerical-integer",
            "numerical-decimal",
        )
    ][:3]
    test2 = Test(
        name="Sample Math Quick Quiz",
        description="A shorter math quiz with every feature toggled on",
        created_by_id=created_by_id,
        organization_id=org_id,
        time_limit=10,
        link=str(uuid.uuid4()),
        **feature_flags,
    )
    session.add(test2)
    session.commit()
    session.refresh(test2)
    assert test2.id is not None
    for rev in math_revisions:
        assert rev.id is not None
        session.add(TestQuestion(test_id=test2.id, question_revision_id=rev.id))
    math_tag_id = next(t.id for t in tags if t.name == "Math")
    assert math_tag_id is not None
    session.add(TestTag(test_id=test2.id, tag_id=math_tag_id))
    session.commit()


def seed(session: Session) -> None:
    if _already_seeded(session):
        logger.info(
            "Sample data already present (marker user %s exists); skipping.",
            MARKER_EMAIL,
        )
        return

    # Prerequisites
    super_admin_role = _get_role(session, "super_admin")
    super_admin_user = session.exec(
        select(User).where(User.role_id == super_admin_role.id)
    ).first()
    if super_admin_user is None or super_admin_user.id is None:
        raise RuntimeError(
            "No superuser found — run `python app/initial_data.py` first."
        )
    creator_id = super_admin_user.id

    state = session.exec(select(State).where(State.name == SAMPLE_STATE_NAME)).first()
    if state is None or state.id is None:
        raise RuntimeError(
            f"State {SAMPLE_STATE_NAME!r} not found — is location data seeded?"
        )
    districts = session.exec(
        select(District).where(District.state_id == state.id).limit(2)
    ).all()
    if len(districts) < 2:
        raise RuntimeError(
            f"Expected at least 2 districts in {SAMPLE_STATE_NAME}, found {len(districts)}."
        )
    district_ids = [d.id for d in districts if d.id is not None]

    org = _get_or_create_organization(session)
    assert org.id is not None

    # Seed default organization settings (idempotent).
    crud_organization_settings.get_or_create(session=session, organization_id=org.id)

    created_users: list[User] = []
    for spec in USERS:
        role = _get_role(session, spec["role"])
        assert role.id is not None
        user = _create_user(
            session,
            role_id=role.id,
            org_id=org.id,
            email=spec["email"],
            full_name=spec["full_name"],
            phone=spec["phone"],
            created_by_id=creator_id,
        )
        assert user.id is not None
        if spec["role"] == "state_admin":
            _assign_user_locations(session, user_id=user.id, state_id=state.id)
        elif spec["role"] == "test_admin":
            _assign_user_locations(
                session,
                user_id=user.id,
                state_id=state.id,
                district_ids=district_ids,
            )
        created_users.append(user)

    test_admin = next(u for u in created_users if u.email == "testadmin@example.com")
    assert test_admin.id is not None

    tags = _create_tags(session, org_id=org.id, created_by_id=test_admin.id)
    entity_type = _create_entities(
        session,
        org_id=org.id,
        created_by_id=test_admin.id,
        state_id=state.id,
        district_id=district_ids[0],
    )
    form = _create_form(
        session,
        org_id=org.id,
        created_by_id=test_admin.id,
        entity_type=entity_type,
    )
    assert form.id is not None
    revisions = _create_sample_questions(
        session, org_id=org.id, created_by_id=test_admin.id, tags=tags
    )
    _create_tests(
        session,
        org_id=org.id,
        created_by_id=test_admin.id,
        revisions=revisions,
        tags=tags,
        state_id=state.id,
        district_ids=district_ids,
        form_id=form.id,
    )

    logger.info("Sample data created successfully.")
    logger.info("Login credentials (password: %s):", DEFAULT_PASSWORD)
    for spec in USERS:
        logger.info("  %-14s  %s", spec["role"], spec["email"])


def main() -> None:
    logger.info("Populating sample data")
    with Session(engine) as session:
        seed(session)
    logger.info("Done.")


if __name__ == "__main__":
    main()
