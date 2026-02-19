#!/usr/bin/env python3
"""
Script to import Block data from CSV file into the database.

CSV format expected:
block_name,district_name,state_name
"""

import csv
import sys
from pathlib import Path

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Block, District, State


def find_district_by_name_and_state(
    session: Session, district_name: str, state_name: str
) -> District | None:
    """Find district by name and state name."""
    return session.exec(
        select(District)
        .join(State)
        .where(District.name == district_name)
        .where(State.name == state_name)
    ).first()


def import_blocks_from_csv(csv_file_path: str) -> None:
    """Import blocks from CSV file."""
    if not Path(csv_file_path).exists():
        print(f"Error: CSV file '{csv_file_path}' not found.")
        sys.exit(1)

    # log errors to csv file for analysis
    error_csv_path = Path(csv_file_path).parent / "errors.csv"
    errors = []

    with Session(engine) as session:
        success_count = 0
        error_count = 0
        duplicate_count = 0

        try:
            with open(csv_file_path, encoding="utf-8") as file:
                csv_reader = csv.DictReader(file)

                # chekc if required columns exists
                expected_headers = {"block_name", "district_name", "state_name"}
                if not expected_headers.issubset(csv_reader.fieldnames or []):
                    print(
                        f"Error: CSV must contain headers: {', '.join(expected_headers)}"
                    )
                    print(f"Found headers: {', '.join(csv_reader.fieldnames or [])}")
                    sys.exit(1)

                for row_num, row in enumerate(
                    csv_reader, start=2
                ):  # start from 2 since header is row 1
                    block_name = row["block_name"].strip()
                    district_name = row["district_name"].strip()
                    state_name = row["state_name"].strip()

                    if not all([block_name, district_name, state_name]):
                        error_msg = f"Empty values - Block: '{block_name}', District: '{district_name}', State: '{state_name}'"
                        print(f"Row {row_num}: Skipping {error_msg}")
                        errors.append(
                            {
                                "row_number": row_num,
                                "block_name": block_name,
                                "district_name": district_name,
                                "state_name": state_name,
                                "error": error_msg,
                            }
                        )
                        error_count += 1
                        continue

                    # find the district
                    district = find_district_by_name_and_state(
                        session, district_name, state_name
                    )

                    if not district:
                        error_msg = f"District '{district_name}' in state '{state_name}' not found"
                        print(f"Row {row_num}: {error_msg}")
                        errors.append(
                            {
                                "row_number": row_num,
                                "block_name": block_name,
                                "district_name": district_name,
                                "state_name": state_name,
                                "error": error_msg,
                            }
                        )
                        error_count += 1
                        continue

                    # check if block already exists
                    existing_block = session.exec(
                        select(Block)
                        .where(Block.name == block_name)
                        .where(Block.district_id == district.id)
                    ).first()

                    if existing_block:
                        print(
                            f"Row {row_num}: Block '{block_name}' already exists in district '{district_name}'"
                        )
                        duplicate_count += 1
                        continue

                    # create new block
                    new_block = Block(
                        name=block_name, district_id=district.id, is_active=True
                    )

                    session.add(new_block)
                    success_count += 1
                    print(
                        f"Row {row_num}: Added block '{block_name}' to district '{district_name}', state '{state_name}'"
                    )

                # commit all changes
                session.commit()

        except Exception as e:
            session.rollback()
            print(f"Error during import: {e}")
            errors.append(
                {
                    "row_number": "N/A",
                    "block_name": "N/A",
                    "district_name": "N/A",
                    "state_name": "N/A",
                    "error": f"System error: {e}",
                }
            )
            error_count += 1

        # write errors to CSV if any errors occurred
        print(f"Debug: Total errors collected: {len(errors)}")
        print(f"Debug: Error CSV path: {error_csv_path}")

        if errors:
            try:
                with open(
                    error_csv_path, "w", newline="", encoding="utf-8"
                ) as error_file:
                    fieldnames = [
                        "row_number",
                        "block_name",
                        "district_name",
                        "state_name",
                        "error",
                    ]
                    writer = csv.DictWriter(error_file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(errors)
                print(f"📝 Error details saved to: {error_csv_path}")
            except Exception as e:
                print(f"❌ Failed to write errors CSV: {e}")
        else:
            print("No errors to write to CSV")

        print("\nImport completed:")
        print(f"✅ Successfully imported: {success_count} blocks")
        print(f"🔄 Duplicates found: {duplicate_count} blocks")
        print(f"❌ Errors/Skipped: {error_count} rows")
        print(
            f"📊 Total processed: {success_count + duplicate_count + error_count} rows"
        )


def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python import_blocks.py <csv_file_path>")
        print("\nCSV format expected:")
        print("block_name,district_name,state_name")
        sys.exit(1)

    csv_file_path = sys.argv[1]
    print(f"Starting import from: {csv_file_path}")
    import_blocks_from_csv(csv_file_path)


if __name__ == "__main__":
    main()
