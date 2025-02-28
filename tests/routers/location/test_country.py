from fastapi.testclient import TestClient


def test_create_country(client: TestClient):
    response = client.post("/location/country/", json={"name": "India"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "India"
