from sqlmodel import Session, create_engine

DATABASE_URL = "sqlite:///sashakt.db"
engine = create_engine(DATABASE_URL, echo=True)


def get_session():
    with Session(engine) as session:
        yield session
