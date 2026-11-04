from app.main import app


def test_no_route_has_trailing_slash() -> None:
    paths = app.openapi()["paths"]
    offending = [path for path in paths if path.endswith("/")]
    assert offending == []
