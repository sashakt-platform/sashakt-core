from sqlmodel import Session

from app.models import Country, State
from app.tests.utils.utils import random_lower_string


def create_random_state(session: Session) -> State:
    country = Country(name=random_lower_string())
    session.add(country)
    session.commit()
    session.refresh(country)
    state = State(
        name=random_lower_string(),
        country_id=country.id,
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state
