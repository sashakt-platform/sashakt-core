from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.location import Block, Country, District, State


def setup_district(session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()

    kerala = State(name="Kerala", country_id=india.id)
    session.add(kerala)
    session.commit()

    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    thrissur = District(name="Thrissur", state_id=kerala.id)
    session.add(ernakulam)
    session.add(thrissur)
    session.commit()

    return ernakulam, thrissur


def test_create_block(client: TestClient, session: Session):
    ernakulam, thrissur = setup_district(session)
    response = client.post(
        "/location/block/", json={"name": "Kovil", "district_id": ernakulam.id}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kovil"
    assert data["district_id"] == ernakulam.id


def test_get_block(client: TestClient, session: Session):
    ernakulam, thrissur = setup_district(session)
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    mayani = Block(name="Mayani", district_id=ernakulam.id)
    kumuram = Block(name="Kumuram", district_id=thrissur.id)
    session.add(kovil)
    session.add(mayani)
    session.add(kumuram)
    session.commit()

    response = client.get("/location/block/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 3

    block_names = {block["name"] for block in data}
    assert "Kovil" in block_names
    assert "Mayani" in block_names
    assert "Kumuram" in block_names

    for block in data:
        if block["name"] == "Kovil":
            assert block["district_id"] == ernakulam.id
        elif block["name"] == "Mayani":
            assert block["district_id"] == ernakulam.id
        elif block["name"] == "Kumuram":
            assert block["district_id"] == thrissur.id


def test_get_block_by_id(client: TestClient, session: Session):
    ernakulam, thrissur = setup_district(session)
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    mayani = Block(name="Mayani", district_id=ernakulam.id)
    kumuram = Block(name="Kumuram", district_id=thrissur.id)
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
    ernakulam, thrissur = setup_district(session)
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    session.add(kovil)
    session.commit()

    response = client.put(
        f"/location/block/{kovil.id}",
        json={"name": "New Kovil", "district_id": kovil.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "New Kovil"
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id
    assert data["district_id"] == ernakulam.id

    response = client.put(
        f"/location/block/{kovil.id}",
        json={"name": kovil.name, "district_id": thrissur.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "New Kovil"
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id
    assert data["district_id"] == thrissur.id
    assert data["district_id"] != ernakulam.id

    response = client.put(
        "/location/block/999",
        json={"name": "Nonexistent Block", "district_id": kovil.id},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}
