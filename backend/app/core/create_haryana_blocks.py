import json
import logging

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Block, District, State

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    with Session(engine) as session:
        with open("app/core/haryana-blocks-create.json") as f:
            data = json.load(f)

        created_blocks = []

        for district_name, block_list in data.items():
            # get district (already exists in DB)
            district = session.exec(
                select(District).where(
                    District.name == district_name,
                    State.name == "Haryana",
                )
            ).first()

            if not district:
                print(f"District {district_name} not found, skipping")
                continue

            for block_name in block_list:
                # create or fetch block
                block = session.exec(
                    select(Block).where(
                        Block.name == block_name, Block.district_id == district.id
                    )
                ).first()

                if not block:
                    block = Block(name=block_name, district_id=district.id)
                    session.add(block)
                    session.commit()
                    session.refresh(block)

            session.commit()

    return {"status": "success", "created_blocks": created_blocks}


def main() -> None:
    logger.info("Creating Blocks in Haryana State")
    init()
    logger.info("Blocks in Haryana State created")


if __name__ == "__main__":
    main()
