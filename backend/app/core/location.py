import json

from sqlmodel import Session

from app.models import Country, District, State


def init_location(session: Session) -> None:
    india = Country(name="India")
    session.add(india)
    session.commit()
    session.refresh(india)

    with open("app/core/states-and-districts.json") as file:
        state_districts = json.load(file)

    for state_district in state_districts["states"]:
        state = State(name=state_district["state"], country_id=india.id)
        session.add(state)
        session.commit()

        for district in state_district["districts"]:
            district = District(name=district, state_id=state.id)
            session.add(district)
            session.commit()
