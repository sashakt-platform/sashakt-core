from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.location import Block, Country, District, State


def setup_district(session: Session):
    india = Country(name="India")
    session.add(india)
    kerala = State(name="Kerala", country_id=1)
    session.add(kerala)
    ernakulam = District(name="Ernakulam", state_id=1)
    thrissur = District(name="Thrissur", state_id=1)
    session.add(ernakulam)
    session.add(thrissur)
    session.commit()
    return ernakulam, thrissur


def test_create_block(client: TestClient, session: Session):
    Ernakulum, Thrissur = setup_district(session)
    response = client.post("/location/block/", json={"name": "Kovil", "district_id": 1})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kovil"
    assert data["id"] == 1


def test_get_block(client: TestClient, session: Session):
    setup_district(session)
    kovil = Block(name="Kovil", district_id=1)
    mayani = Block(name="Mayani", district_id=1)
    kumuram = Block(name="Kumuram", district_id=2)
    session.add(kovil)
    session.add(mayani)
    session.add(kumuram)
    session.commit()
    response = client.get("/location/block/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 3
    assert data[0]["name"] == "Kovil"
    assert data[1]["name"] == "Mayani"
    assert data[2]["name"] == "Kumuram"
    assert data[0]["district_id"] == 1
    assert data[1]["district_id"] == 1
    assert data[2]["district_id"] == 2


def test_get_block_by_id(client: TestClient, session: Session):
    setup_district(session)
    kovil = Block(name="Kovil", district_id=1)
    mayani = Block(name="Mayani", district_id=1)
    kumuram = Block(name="Kumuram", district_id=2)
    session.add(kovil)
    session.add(mayani)
    session.add(kumuram)
    session.commit()

    response = client.get(f"/location/block/{kovil.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kovil"
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id

    response = client.get(f"/location/block/{mayani.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Mayani"
    assert data["id"] == mayani.id
    assert data["district_id"] == mayani.district_id

    response = client.get(f"/location/block/{kumuram.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kumuram"
    assert data["id"] == kumuram.id
    assert data["district_id"] == kumuram.district_id

    response = client.get("/location/block/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}


def test_update_block(client: TestClient, session: Session):
    setup_district(session)
    kovil = Block(name="Kovil", district_id=1)
    session.add(kovil)
    session.commit()

    response = client.put(f"/location/block/{kovil.id}", json={"name": "New Kovil"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "New Kovil"
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id

    response = client.put("/location/block/999", json={"name": "Nonexistent Block"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}
