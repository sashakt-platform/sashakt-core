from fastapi.testclient import TestClient

import pytest

from app.main import app

@pytest.fixture(name="client")
def _client():
    return TestClient(app)

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Sashakt": "Platform"}
