import json
import logging

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models import Block, District, State
from app.models.entity import Entity, EntityType
from app.models.organization import Organization
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.full_name == settings.FIRST_SUPERUSER_FULLNAME)
        ).first()

        organization = session.exec(
            select(Organization).where(Organization.name == "Veddis Foundation")
        ).first()

        clf_entity_type = session.exec(
            select(EntityType).where(EntityType.name == "CLF")
        ).first()
        if not clf_entity_type:
            clf_entity_type = EntityType(
                name="CLF",
                description="Cluster Level Federation",
                organization_id=organization.id,
                created_by_id=user.id,
            )
            session.add(clf_entity_type)
            session.commit()
            session.refresh(clf_entity_type)
            logger.info("Created CLF entity type")

        with open("app/core/haryana-clf-create.json") as f:
            data = json.load(f)

        created_clfs = []
        state = session.exec(select(State).where(State.name == "Haryana")).first()
        if not state:
            logger.error("State Haryana not found. Please create the state first.")
            return {"status": "error", "message": "State Haryana not found."}
        state_id = state.id

        for item in data:
            # Get district
            district = session.exec(
                select(District).where(
                    District.name == item["district"], District.state_id == state_id
                )
            ).first()
            if not district:
                print(f"District {item['district']} not found. Skipping...")
                continue

            # Get block
            block = session.exec(
                select(Block).where(
                    Block.name == item["block"], Block.district_id == district.id
                )
            ).first()
            if not block:
                print(
                    f"Block {item['block']} in district {item['district']} not found. Skipping..."
                )
                continue

            # Check if CLF already exists
            clf_exists = session.exec(
                select(Entity).where(
                    Entity.name == item["clf"],
                    Entity.district_id == district.id,
                    Entity.block_id == block.id,
                )
            ).first()

            if clf_exists:
                print(f"CLF {item['clf']} already exists. Skipping...")
                continue

            # Create new CLF
            clf = Entity(
                name=item["clf"],
                entity_type_id=clf_entity_type.id,
                state_id=state_id,
                district_id=district.id,
                block_id=block.id,
                created_by_id=user.id,
            )
            session.add(clf)
            session.commit()
            session.refresh(clf)
            created_clfs.append(clf)

    return {"status": "success", "created_clfs": created_clfs}


def main() -> None:
    logger.info("Creating CLFs in Haryana State")
    init()
    logger.info("CLFs in Haryana State created")


if __name__ == "__main__":
    main()
