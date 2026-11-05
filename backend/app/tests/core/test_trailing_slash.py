from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_no_route_has_trailing_slash() -> None:
    paths = app.openapi()["paths"]
    offending = [path for path in paths if path.endswith("/")]
    assert offending == []


def test_trailing_slash_request_is_not_redirected(client: TestClient) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/utils/health-check/", follow_redirects=False
    )
    assert response.status_code == 404
