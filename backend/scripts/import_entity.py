#!/usr/bin/env python3
"""
Script to import Entity data from CSV file into the database.

CSV format expected:
entity_name,entity_type_name,organization_name,block_name,district_name,state_name
"""

import csv
import sys
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models import Block, District, Entity, EntityType, Organization, State
from app.models.user import User


def find_block(
    session: Session, block_name: str, district_name: str, state_name: str
) -> Block | None:
    """Find block by name, district, and state."""
    return session.exec(
        select(Block)
        .join(District, Block.district_id == District.id)
        .join(State, District.state_id == State.id)
        .where(Block.name == block_name)
        .where(District.name == district_name)
        .where(State.name == state_name)
    ).first()


def find_district(
    session: Session, district_name: str, state_name: str
) -> District | None:
    """Find district by name and state name."""
    return session.exec(
        select(District)
        .join(State)
        .where(District.name == district_name)
        .where(State.name == state_name)
    ).first()


def find_state(session: Session, state_name: str) -> State | None:
    """Find state by name."""
    return session.exec(select(State).where(State.name == state_name)).first()


def get_superuser_id(session: Session) -> int:
    user = session.exec(
        select(User).where(User.full_name == settings.FIRST_SUPERUSER_FULLNAME)
    ).first()
    if not user:
        raise ValueError("Superuser not found")
    return user.id


def find_entity_type(
    session: Session, entity_type_name: str, organization_id: int
) -> EntityType | None:
    """Find entity type by name."""
    return session.exec(
        select(EntityType).where(
            EntityType.name == entity_type_name,
            EntityType.organization_id == organization_id,
        )
    ).first()


def find_organization(session: Session, organization_name: str) -> Organization | None:
    """Find organization by name."""
    return session.exec(
        select(Organization).where(Organization.name == organization_name)
    ).first()


def import_entities_from_csv(csv_file_path: str) -> None:
    """Import entities from CSV file."""
    if not Path(csv_file_path).exists():
        print(f"Error: CSV file '{csv_file_path}' not found.")
        sys.exit(1)

    error_csv_path = Path(csv_file_path).parent / "entity_import_errors.csv"
    errors = []

    with Session(engine) as session:
        success_count = 0
        duplicate_count = 0
        error_count = 0

        superuser_id = get_superuser_id(session)

        try:
            with open(csv_file_path, encoding="utf-8") as file:
                csv_reader = csv.DictReader(file)

                expected_headers = {
                    "entity_name",
                    "entity_type_name",
                    "organization_name",
                    "block_name",
                    "district_name",
                    "state_name",
                }
                if not expected_headers.issubset(csv_reader.fieldnames or []):
                    print(
                        f"Error: CSV must contain headers: {', '.join(expected_headers)}"
                    )
                    print(f"Found headers: {', '.join(csv_reader.fieldnames or [])}")
                    sys.exit(1)

                for row_num, row in enumerate(csv_reader, start=2):
                    entity_name = row["entity_name"].strip()
                    entity_type_name = row["entity_type_name"].strip()
                    organization_name = row["organization_name"].strip()
                    block_name = row["block_name"].strip() or None
                    district_name = row["district_name"].strip() or None
                    state_name = row["state_name"].strip() or None

                    if not all(
                        [
                            entity_name,
                            entity_type_name,
                            organization_name,
                            block_name,
                            district_name,
                            state_name,
                        ]
                    ):
                        error_msg = "Empty values in row"
                        print(f"Row {row_num}: Skipping {error_msg}")
                        errors.append(
                            {**row, "row_number": row_num, "error": error_msg}
                        )
                        error_count += 1
                        continue

                    block = (
                        find_block(session, block_name, district_name, state_name)
                        if block_name and district_name and state_name
                        else None
                    )
                    district = (
                        find_district(session, district_name, state_name)
                        if district_name and state_name
                        else None
                    )

                    state = find_state(session, state_name) if state_name else None

                    organization = find_organization(session, organization_name)

                    if not organization:
                        error_msg = f"Organization '{organization_name}' not found"
                        print(f"Row {row_num}: {error_msg}")
                        errors.append(
                            {**row, "row_number": row_num, "error": error_msg}
                        )
                        error_count += 1
                        continue

                    entity_type = find_entity_type(
                        session, entity_type_name, organization.id
                    )

                    if not entity_type:
                        error_msg = f"Entity type '{entity_type_name}' not found"
                        print(f"Row {row_num}: {error_msg}")
                        errors.append(
                            {**row, "row_number": row_num, "error": error_msg}
                        )
                        error_count += 1
                        continue

                    existing_entity = session.exec(
                        select(Entity)
                        .where(Entity.name == entity_name)
                        .where(Entity.entity_type_id == entity_type.id)
                        .where(Entity.block_id == block.id if block else None)
                        .where(Entity.district_id == district.id if district else None)
                        .where(Entity.state_id == state.id if state else None)
                    ).first()

                    if existing_entity:
                        print(f"Row {row_num}: Entity '{entity_name}' already exists")
                        duplicate_count += 1
                        continue

                    new_entity = Entity(
                        name=entity_name,
                        entity_type_id=entity_type.id,
                        block_id=block.id if block else None,
                        district_id=district.id if district else None,
                        state_id=state.id if state else None,
                        is_active=True,
                        created_by_id=superuser_id,
                    )

                    session.add(new_entity)
                    success_count += 1
                    print(f"Row {row_num}: Added entity '{entity_name}'")

                session.commit()

        except Exception as e:
            session.rollback()
            print(f"Error during import: {e}")
            errors.append({"row_number": "N/A", "error": f"System error: {e}"})
            error_count += 1

        if errors:
            with open(error_csv_path, "w", newline="", encoding="utf-8") as error_file:
                fieldnames = list(expected_headers) + ["row_number", "error"]
                writer = csv.DictWriter(error_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(errors)
            print(f"📝 Error details saved to: {error_csv_path}")

        print("\nImport completed:")
        print(f"✅ Successfully imported: {success_count} entities")
        print(f"🔄 Duplicates found: {duplicate_count} entities")
        print(f"❌ Errors/Skipped: {error_count} rows")
        print(
            f"📊 Total processed: {success_count + duplicate_count + error_count} rows"
        )


def main():
    if len(sys.argv) != 2:
        print("Usage: python import_entities.py <csv_file_path>")
        print("\nCSV format expected:")
        print(
            "entity_name,entity_type_name,organization_name,block_name,district_name,state_name"
        )
        sys.exit(1)

    csv_file_path = sys.argv[1]
    print(f"Starting entity import from: {csv_file_path}")
    import_entities_from_csv(csv_file_path)


if __name__ == "__main__":
    main()
