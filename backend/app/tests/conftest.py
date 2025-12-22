from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.tests.utils.user import authentication_token_from_email, get_user_token
from app.tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    """Initialize database with seed data once per test session."""
    with Session(engine) as session:
        init_db(session)
    yield


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Create a transactional test session with automatic rollback.

    Uses SQLAlchemy's recommended pattern for test isolation:
    1. Start a transaction at the connection level
    2. Bind the session with join_transaction_mode="create_savepoint"
    3. Session commits become savepoints instead of real commits
    4. Rollback the outer transaction at the end, undoing all changes
    """
    connection = engine.connect()
    trans = connection.begin()

    # join_transaction_mode ensures session.commit() creates savepoints
    # instead of real commits, as we are joining an existing transaction
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    yield session

    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Test client that uses the transactional session."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="function")
def get_user_superadmin_token(db: Session) -> dict[str, str]:
    return get_user_token(db=db, role="super_admin")


@pytest.fixture(scope="function")
def get_user_systemadmin_token(db: Session) -> dict[str, str]:
    return get_user_token(db=db, role="system_admin")


@pytest.fixture(scope="function")
def get_user_stateadmin_token(db: Session) -> dict[str, str]:
    return get_user_token(db=db, role="state_admin")


@pytest.fixture(scope="function")
def get_user_testadmin_token(db: Session) -> dict[str, str]:
    return get_user_token(db=db, role="test_admin")


@pytest.fixture(scope="function")
def get_user_candidate_token(db: Session) -> dict[str, str]:
    return get_user_token(db=db, role="candidate")


@pytest.fixture(scope="function")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
