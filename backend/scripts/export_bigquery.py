#!/usr/bin/env python3
"""
BigQuery Data Export Script

This script exports data from PostgreSQL to BigQuery for one or all organizations.
It can perform full or incremental syncs based on the options provided.

Usage:
    python export_bigquery.py --org-id 1 --incremental
    python export_bigquery.py --all-orgs --full-sync
    python export_bigquery.py --test-connections
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

# Add the app directory to the path so we can import our modules
app_path = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_path))

from services.data_sync import data_sync_service  # noqa: E402

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/bigquery_export.log"),
    ],
)

logger = logging.getLogger(__name__)


def test_all_connections() -> None:
    """Test connections for all configured providers."""
    logger.info("Testing all provider connections...")

    try:
        # Get all organization providers and test their connections
        from core.db import engine
        from models import OrganizationProvider, Provider
        from sqlmodel import Session, select

        with Session(engine) as session:
            statement = (
                select(OrganizationProvider, Provider)
                .join(Provider)
                .where(OrganizationProvider.is_enabled, Provider.is_active)
            )
            results = session.exec(statement).all()

            if not results:
                logger.info("No active provider configurations found.")
                return

            success_count = 0
            total_count = len(results)

            for org_provider, provider in results:
                org_id = org_provider.organization_id
                provider_id = provider.id
                provider_name = provider.name

                logger.info(
                    f"Testing connection for Organization {org_id}, Provider {provider_name}..."
                )

                try:
                    success = data_sync_service.test_provider_connection(
                        org_id, provider_id
                    )
                    if success:
                        logger.info(
                            f"✓ Connection successful for Organization {org_id}, Provider {provider_name}"
                        )
                        success_count += 1
                    else:
                        logger.error(
                            f"✗ Connection failed for Organization {org_id}, Provider {provider_name}"
                        )
                except Exception as e:
                    logger.error(
                        f"✗ Connection test error for Organization {org_id}, Provider {provider_name}: {e}"
                    )

            logger.info(
                f"Connection test summary: {success_count}/{total_count} successful"
            )

    except Exception as e:
        logger.error(f"Error during connection testing: {e}")
        sys.exit(1)


def get_table_record_counts(org_id: int, incremental: bool = True) -> dict[str, int]:
    """Get detailed record counts per table for an organization."""
    try:
        extracted_data = data_sync_service._extract_organization_data(
            org_id, incremental
        )
        return {
            table_name: len(records) for table_name, records in extracted_data.items()
        }
    except Exception as e:
        logger.warning(f"Could not get detailed table counts: {e}")
        return {}


def export_organization_data(org_id: int, incremental: bool = True) -> None:
    """Export data for a specific organization."""
    logger.info(
        f"Starting data export for organization {org_id} (incremental={incremental})"
    )

    try:
        # Get detailed table record counts before sync
        table_counts = get_table_record_counts(org_id, incremental)

        results = data_sync_service.sync_organization_data(org_id, incremental)

        if not results:
            logger.warning(f"No active providers found for organization {org_id}")
            return

        # Log results for each provider
        for provider_key, result in results.items():
            if result.success:
                logger.info(
                    f"✓ Export successful for {provider_key}: "
                    f"{result.records_exported} records exported, "
                    f"{len(result.tables_created)} tables created, "
                    f"{len(result.tables_updated)} tables updated"
                )

                # Log detailed table information
                if table_counts:
                    non_empty_tables = {
                        name: count for name, count in table_counts.items() if count > 0
                    }
                    empty_tables = {
                        name: count
                        for name, count in table_counts.items()
                        if count == 0
                    }

                    logger.info(f"  📊 Table-by-table breakdown for {provider_key}:")
                    logger.info(
                        f"    📈 Tables with data ({len(non_empty_tables)}/{len(table_counts)}):"
                    )

                    total_records = 0
                    if non_empty_tables:
                        for table_name, record_count in sorted(
                            non_empty_tables.items()
                        ):
                            status = (
                                "created"
                                if table_name in result.tables_created
                                else "updated"
                            )
                            logger.info(
                                f"      • {table_name}: {record_count:,} records ({status})"
                            )
                            total_records += record_count
                    else:
                        logger.info("      (no tables with data)")

                    if empty_tables:
                        logger.info(f"    📭 Empty tables ({len(empty_tables)}):")
                        empty_table_names = ", ".join(sorted(empty_tables.keys()))
                        logger.info(f"      {empty_table_names}")

                    if total_records != result.records_exported:
                        logger.warning(
                            f"    ⚠️  Record count mismatch: expected {total_records:,}, "
                            f"actual {result.records_exported:,}"
                        )
            else:
                logger.error(
                    f"✗ Export failed for {provider_key}: {result.error_message}"
                )

        logger.info(f"Data export completed for organization {org_id}")

    except Exception as e:
        logger.error(f"Error during data export for organization {org_id}: {e}")
        sys.exit(1)


def export_all_organizations_data(incremental: bool = True) -> None:
    """Export data for all organizations."""
    logger.info(
        f"Starting data export for all organizations (incremental={incremental})"
    )

    try:
        results = data_sync_service.sync_all_organizations_data(incremental)

        if not results:
            logger.warning("No organizations with active providers found")
            return

        total_orgs = len(results)
        successful_orgs = 0
        total_records_across_orgs = 0

        for org_id, org_results in results.items():
            logger.info(f"📋 Organization {org_id} results:")

            # Get detailed table counts for this organization
            table_counts = get_table_record_counts(org_id, incremental)

            org_success = True
            org_total_records = 0

            for provider_key, result in org_results.items():
                if result.success:
                    logger.info(
                        f"  ✓ {provider_key}: {result.records_exported:,} records exported, "
                        f"{len(result.tables_created)} tables created, "
                        f"{len(result.tables_updated)} tables updated"
                    )
                    org_total_records += result.records_exported

                    # Log detailed table breakdown for each org
                    if table_counts:
                        non_empty_tables = {
                            name: count
                            for name, count in table_counts.items()
                            if count > 0
                        }
                        if non_empty_tables:
                            logger.info(
                                f"    📊 Tables with data: {len(non_empty_tables)}/{len(table_counts)}"
                            )
                            for table_name, record_count in sorted(
                                non_empty_tables.items()
                            ):
                                status = (
                                    "created"
                                    if table_name in result.tables_created
                                    else "updated"
                                )
                                logger.info(
                                    f"      • {table_name}: {record_count:,} records ({status})"
                                )
                        else:
                            logger.info(
                                "    📊 No tables with data for this organization"
                            )
                else:
                    logger.error(f"  ✗ {provider_key}: {result.error_message}")
                    org_success = False

            if org_success:
                successful_orgs += 1
                total_records_across_orgs += org_total_records

        logger.info("=" * 60)
        logger.info(
            f"🎯 Export summary: {successful_orgs}/{total_orgs} organizations exported successfully"
        )
        logger.info(
            f"📊 Total records exported across all organizations: {total_records_across_orgs:,}"
        )

    except Exception as e:
        logger.error(f"Error during bulk data export: {e}")
        sys.exit(1)


def print_export_summary(results: dict[str, Any]) -> None:
    """Print a formatted summary of export results."""
    print("\n" + "=" * 60)
    print("EXPORT SUMMARY")
    print("=" * 60)

    for provider_key, result in results.items():
        print(f"\nProvider: {provider_key}")
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")

        if result.success:
            print(f"Records Exported: {result.records_exported}")
            print(f"Tables Created: {len(result.tables_created)}")
            print(f"Tables Updated: {len(result.tables_updated)}")
            if result.tables_created:
                print(f"  Created: {', '.join(result.tables_created)}")
            if result.tables_updated:
                print(f"  Updated: {', '.join(result.tables_updated)}")
        else:
            print(f"Error: {result.error_message}")

        print(f"Sync Time: {result.sync_timestamp}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Sashakt data to BigQuery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_bigquery.py --org-id 1 --incremental
  python export_bigquery.py --all-orgs --full-sync
  python export_bigquery.py --test-connections
        """,
    )

    # Mutually exclusive group for target selection
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--org-id", type=int, help="Export data for a specific organization ID"
    )
    target_group.add_argument(
        "--all-orgs", action="store_true", help="Export data for all organizations"
    )
    target_group.add_argument(
        "--test-connections", action="store_true", help="Test all provider connections"
    )

    # Sync type options
    sync_group = parser.add_mutually_exclusive_group()
    sync_group.add_argument(
        "--incremental",
        action="store_true",
        default=True,
        help="Perform incremental sync (default)",
    )
    sync_group.add_argument(
        "--full-sync", action="store_true", help="Perform full sync (replaces all data)"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle different execution modes
    if args.test_connections:
        test_all_connections()
    elif args.org_id:
        incremental = not args.full_sync
        export_organization_data(args.org_id, incremental)
    elif args.all_orgs:
        incremental = not args.full_sync
        export_all_organizations_data(incremental)

    logger.info("Script execution completed")


if __name__ == "__main__":
    main()
