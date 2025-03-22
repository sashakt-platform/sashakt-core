from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import (
    Block,
    Candidate,
    CandidateTest,
    CandidateTestAnswer,
    Country,
    District,
    Organization,
    Question,
    Role,
    State,
    Tag,
    TagType,
    Test,
    TestQuestion,
    TestState,
    TestTag,
    User,
)
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="function", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(Tag)
        session.execute(statement)
        statement = delete(TagType)
        session.execute(statement)
        statement = delete(Candidate)
        session.execute(statement)
        statement = delete(TestState)
        session.execute(statement)
        statement = delete(TestTag)
        session.execute(statement)
        statement = delete(TestQuestion)
        session.execute(statement)
        statement = delete(Test)
        session.execute(statement)

        statement = delete(Question)
        session.execute(statement)

        statement = delete(Role)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        statement = delete(Organization)
        session.execute(statement)
        statement = delete(Block)
        session.execute(statement)
        statement = delete(District)
        session.execute(statement)
        statement = delete(State)
        session.execute(statement)
        statement = delete(Country)
        session.execute(statement)
        statement = delete(CandidateTest)
        session.execute(statement)
        statement = delete(CandidateTestAnswer)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
