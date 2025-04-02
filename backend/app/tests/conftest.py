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
    QuestionLocation,
    QuestionRevision,
    QuestionTag,
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


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        # Delete in proper order - dependent tables first
        try:
            statement = delete(QuestionTag)
            session.execute(statement)
            statement = delete(Tag)
            session.execute(statement)
            statement = delete(TagType)
            session.execute(statement)
            # First delete candidate test answers
            statement = delete(CandidateTestAnswer)
            session.execute(statement)
            # Then delete candidate tests
            statement = delete(CandidateTest)
            session.execute(statement)
            # Delete test dependencies
            statement = delete(TestState)
            session.execute(statement)
            statement = delete(TestTag)
            session.execute(statement)
            statement = delete(TestQuestion)
            session.execute(statement)
            # Delete question dependencies

            statement = delete(QuestionRevision)
            session.execute(statement)
            statement = delete(QuestionLocation)
            session.execute(statement)
            # Delete main objects
            statement = delete(Test)
            session.execute(statement)
            statement = delete(Question)
            session.execute(statement)
            statement = delete(Candidate)
            session.execute(statement)
            statement = delete(Role)
            session.execute(statement)
            statement = delete(User)
            session.execute(statement)
            statement = delete(Organization)
            session.execute(statement)
            # Delete location hierarchy
            statement = delete(Block)
            session.execute(statement)
            statement = delete(District)
            session.execute(statement)
            statement = delete(State)
            session.execute(statement)
            statement = delete(Country)
            session.execute(statement)
            session.commit()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            session.rollback()


@pytest.fixture(scope="module")  # Changed from module to function
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")  # Changed from module to function
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    try:
        headers = get_superuser_token_headers(client)
        if not headers or "Authorization" not in headers:
            print(
                "Warning: Superuser token not obtained. Check login endpoint and credentials."
            )
            return {"Authorization": "Bearer dummy_token_for_tests"}
        return headers
    except Exception as e:
        print(f"Error getting superuser token: {e}")
        return {"Authorization": "Bearer dummy_token_for_tests"}


@pytest.fixture(scope="module")  # Changed from module to function
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    try:
        return authentication_token_from_email(
            client=client, email=settings.EMAIL_TEST_USER, db=db
        )
    except Exception as e:
        print(f"Error getting normal user token: {e}")
        return {"Authorization": "Bearer dummy_token_for_tests"}
