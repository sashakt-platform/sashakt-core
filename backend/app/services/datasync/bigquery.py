import json
from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.timezone import get_timezone_aware_now
from app.services.datasync.base import SyncResult, TableSchema


class BigQueryService:
    """Direct BigQuery data synchronization service"""

    def __init__(self, organization_id: int, config: dict[str, Any]):
        self.organization_id = organization_id
        self.config = config
        self._client: bigquery.Client | None = None

    def initialize_client(self) -> bigquery.Client:
        if self._client is None:
            # Extract service account credentials from the flattened config
            credentials_info = {
                "type": self.config["type"],
                "project_id": self.config["project_id"],
                "private_key_id": self.config["private_key_id"],
                "private_key": self.config["private_key"],
                "client_email": self.config["client_email"],
                "client_id": self.config["client_id"],
                "auth_uri": self.config["auth_uri"],
                "token_uri": self.config["token_uri"],
                "auth_provider_x509_cert_url": self.config[
                    "auth_provider_x509_cert_url"
                ],
                "client_x509_cert_url": self.config["client_x509_cert_url"],
            }
            credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                credentials_info
            )
            self._client = bigquery.Client(
                project=self.config["project_id"], credentials=credentials
            )
        return self._client

    def dataset_exists(self) -> bool:
        """Check if the BigQuery dataset exists"""
        try:
            client = self.initialize_client()
            dataset_ref = client.dataset(self.config["dataset_id"])
            client.get_dataset(dataset_ref)
            return True
        except Exception:
            return False

    def get_table_sync_metadata(
        self, table_name: str
    ) -> tuple[datetime | None, int | None]:
        """Get last sync timestamp and last synced ID for a specific table"""
        try:
            client = self.initialize_client()
            metadata_table = f"{self.config['dataset_id']}.sync_metadata"

            query = f"""
            SELECT last_sync_timestamp, last_synced_id
            FROM `{self.config["project_id"]}.{metadata_table}`
            WHERE table_name = @table_name
            ORDER BY last_sync_timestamp DESC
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("table_name", "STRING", table_name)
                ]
            )

            query_job = client.query(query, job_config=job_config)
            results = list(query_job.result())

            if results:
                row = results[0]
                last_sync_timestamp = row.last_sync_timestamp
                # Convert timezone-aware timestamp to naive (assume UTC)
                if last_sync_timestamp and last_sync_timestamp.tzinfo is not None:
                    last_sync_timestamp = last_sync_timestamp.replace(tzinfo=None)
                return last_sync_timestamp, row.get("last_synced_id")
            else:
                return None, None

        except Exception as e:
            print(f"Error getting table sync metadata: {e}")
            return None, None

    def get_table_name(self, base_name: str) -> str:
        """Get the table name"""
        return base_name

    def test_connection(self) -> bool:
        try:
            client = self.initialize_client()
            query = "SELECT 1 as test"
            query_job = client.query(query)
            result = list(query_job.result())
            return len(result) == 1 and result[0].test == 1
        except Exception:
            return False

    def create_dataset_if_not_exists(self) -> bool:
        try:
            client = self.initialize_client()
            dataset_id = self.config["dataset_id"]
            dataset_ref = client.dataset(dataset_id)

            try:
                client.get_dataset(dataset_ref)
                return True
            except Exception:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = "US"
                dataset.description = (
                    f"Sashakt data export for organization {self.organization_id}"
                )
                client.create_dataset(dataset)
                return True
        except Exception:
            return False

    def create_table_if_not_exists(self, schema: TableSchema) -> bool:
        try:
            client = self.initialize_client()
            dataset_id = self.config["dataset_id"]
            table_ref = client.dataset(dataset_id).table(schema.table_name)

            try:
                client.get_table(table_ref)
                return False
            except Exception:
                table = bigquery.Table(table_ref)

                bq_schema = []
                for column in schema.columns:
                    field = bigquery.SchemaField(
                        column["name"],
                        column["type"],
                        mode=column.get("mode", "NULLABLE"),
                        description=column.get("description", ""),
                    )
                    bq_schema.append(field)

                table.schema = bq_schema

                if schema.partition_field:
                    table.time_partitioning = bigquery.TimePartitioning(
                        type_=bigquery.TimePartitioningType.DAY,
                        field=schema.partition_field,
                    )

                if schema.clustering_fields:
                    table.clustering_fields = schema.clustering_fields

                client.create_table(table)
                return True
        except Exception:
            return False

    def export_data(
        self,
        table_name: str,
        data: list[dict[str, Any]],
        schema: TableSchema,
        mode: str = "append",
    ) -> int:
        try:
            client = self.initialize_client()
            dataset_id = self.config["dataset_id"]
            table_ref = client.dataset(dataset_id).table(table_name)

            job_config = bigquery.LoadJobConfig()
            job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
            job_config.autodetect = False

            if mode == "replace":
                job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
            else:
                job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND

            bq_schema = []
            for column in schema.columns:
                field = bigquery.SchemaField(
                    column["name"], column["type"], mode=column.get("mode", "NULLABLE")
                )
                bq_schema.append(field)
            job_config.schema = bq_schema

            # Convert data for BigQuery (keeping as dict objects, not JSON strings)
            processed_data: list[dict[str, Any]] = []
            for record in data:
                processed_record: dict[str, Any] = {}
                for key, value in record.items():
                    # Handle datetime strings and other types
                    if value is None:
                        processed_record[key] = None
                    elif isinstance(value, dict | list):
                        processed_record[key] = json.dumps(value)
                    else:
                        processed_record[key] = (
                            str(value)
                            if not isinstance(value, bool | int | float)
                            else value
                        )
                processed_data.append(processed_record)

            job = client.load_table_from_json(
                processed_data, table_ref, job_config=job_config
            )
            job.result()

            return len(data)
        except Exception as e:
            print(f"BigQuery export_data error: {str(e)}")
            import traceback

            traceback.print_exc()
            return 0

    def update_sync_metadata(
        self, table_name: str, timestamp: datetime, last_synced_id: int | None = None
    ) -> bool:
        try:
            client = self.initialize_client()
            dataset_id = self.config["dataset_id"]
            metadata_table = f"{dataset_id}.sync_metadata"

            self._create_sync_metadata_table_if_not_exists()

            query = f"""
            MERGE `{metadata_table}` T
            USING (SELECT @table_name as table_name, @timestamp as last_sync_timestamp, @last_synced_id as last_synced_id, @timestamp as created_at, @timestamp as updated_at) S
            ON T.table_name = S.table_name
            WHEN MATCHED THEN
                UPDATE SET last_sync_timestamp = S.last_sync_timestamp, last_synced_id = S.last_synced_id, updated_at = S.updated_at
            WHEN NOT MATCHED THEN
                INSERT (table_name, last_sync_timestamp, last_synced_id, created_at, updated_at)
                VALUES (S.table_name, S.last_sync_timestamp, S.last_synced_id, S.created_at, S.updated_at)
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("table_name", "STRING", table_name),
                    bigquery.ScalarQueryParameter("timestamp", "TIMESTAMP", timestamp),
                    bigquery.ScalarQueryParameter(
                        "last_synced_id", "INTEGER", last_synced_id
                    ),
                ]
            )

            query_job = client.query(query, job_config=job_config)
            query_job.result()
            return True
        except Exception as e:
            print(f"BigQuery update_sync_metadata error: {str(e)}")
            import traceback

            traceback.print_exc()
            return False

    def _create_sync_metadata_table_if_not_exists(self) -> bool:
        try:
            client = self.initialize_client()
            dataset_id = self.config["dataset_id"]
            table_ref = client.dataset(dataset_id).table("sync_metadata")

            try:
                client.get_table(table_ref)
                return True
            except Exception:
                schema = [
                    bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField(
                        "last_sync_timestamp", "TIMESTAMP", mode="REQUIRED"
                    ),
                    bigquery.SchemaField("last_synced_id", "INTEGER", mode="NULLABLE"),
                    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
                ]

                table = bigquery.Table(table_ref, schema=schema)
                client.create_table(table)
                return True
        except Exception as e:
            print(f"BigQuery _create_sync_metadata_table_if_not_exists error: {str(e)}")
            import traceback

            traceback.print_exc()
            return False

    def _get_table_schema(self, table_name: str) -> TableSchema:
        schemas = {
            "users": TableSchema(
                table_name=self.get_table_name("users"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "email", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "full_name", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "phone", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "role_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "organization_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
            ),
            "tests": TableSchema(
                table_name=self.get_table_name("tests"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "description", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "time_limit", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "start_time", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "end_time", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "marks", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_by_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
            ),
            "questions": TableSchema(
                table_name=self.get_table_name("questions"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "last_revision_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "organization_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
            ),
            "candidates": TableSchema(
                table_name=self.get_table_name("candidates"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "identity", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "user_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
            ),
            "candidate_test_answers": TableSchema(
                table_name=self.get_table_name("candidate_test_answers"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {
                        "name": "candidate_test_id",
                        "type": "INTEGER",
                        "mode": "REQUIRED",
                    },
                    {
                        "name": "question_revision_id",
                        "type": "INTEGER",
                        "mode": "REQUIRED",
                    },
                    {"name": "response", "type": "JSON", "mode": "NULLABLE"},
                    {"name": "time_spent", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "visited", "type": "BOOLEAN", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["candidate_test_id", "question_revision_id"],
            ),
            "candidate_tests": TableSchema(
                table_name=self.get_table_name("candidate_tests"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "candidate_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "test_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "start_time", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "end_time", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "is_submitted", "type": "BOOLEAN", "mode": "NULLABLE"},
                    {"name": "consent", "type": "BOOLEAN", "mode": "NULLABLE"},
                    {"name": "device", "type": "JSON", "mode": "NULLABLE"},
                    {
                        "name": "question_revision_ids",
                        "type": "JSON",
                        "mode": "NULLABLE",
                    },
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["candidate_id", "test_id"],
            ),
            "states": TableSchema(
                table_name=self.get_table_name("states"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "country_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
            ),
            "districts": TableSchema(
                table_name=self.get_table_name("districts"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "state_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["state_id"],
            ),
            "blocks": TableSchema(
                table_name=self.get_table_name("blocks"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "district_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["district_id"],
            ),
            "entities": TableSchema(
                table_name=self.get_table_name("entities"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "description", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "entity_type_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "state_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "district_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "block_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_by_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["entity_type_id"],
            ),
            "entity_types": TableSchema(
                table_name=self.get_table_name("entity_types"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "description", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "organization_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_by_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["organization_id"],
            ),
            "tags": TableSchema(
                table_name=self.get_table_name("tags"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "description", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "tag_type_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "organization_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_by_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["organization_id", "tag_type_id"],
            ),
            "tag_types": TableSchema(
                table_name=self.get_table_name("tag_types"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "description", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "organization_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "is_deleted", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_by_id", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["organization_id"],
            ),
            "question_tags": TableSchema(
                table_name=self.get_table_name("question_tags"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "question_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "tag_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["question_id", "tag_id"],
            ),
            "question_revisions": TableSchema(
                table_name=self.get_table_name("question_revisions"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "question_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "created_by_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "question_text", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "instructions", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "question_type", "type": "STRING", "mode": "REQUIRED"},
                    {"name": "options", "type": "JSON", "mode": "NULLABLE"},
                    {"name": "correct_answer", "type": "JSON", "mode": "NULLABLE"},
                    {
                        "name": "subjective_answer_limit",
                        "type": "INTEGER",
                        "mode": "NULLABLE",
                    },
                    {"name": "is_mandatory", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "is_active", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "marking_scheme", "type": "JSON", "mode": "NULLABLE"},
                    {"name": "solution", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "media", "type": "JSON", "mode": "NULLABLE"},
                    {"name": "is_deleted", "type": "BOOLEAN", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                    {"name": "modified_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["question_id", "created_by_id"],
            ),
            "candidate_test_profiles": TableSchema(
                table_name=self.get_table_name("candidate_test_profiles"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {
                        "name": "candidate_test_id",
                        "type": "INTEGER",
                        "mode": "REQUIRED",
                    },
                    {"name": "entity_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["candidate_test_id", "entity_id"],
            ),
            "test_questions": TableSchema(
                table_name=self.get_table_name("test_questions"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "test_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {
                        "name": "question_revision_id",
                        "type": "INTEGER",
                        "mode": "REQUIRED",
                    },
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["test_id", "question_revision_id"],
            ),
            "test_tags": TableSchema(
                table_name=self.get_table_name("test_tags"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "test_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "tag_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["test_id", "tag_id"],
            ),
            "test_districts": TableSchema(
                table_name=self.get_table_name("test_districts"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "test_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "district_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["test_id", "district_id"],
            ),
            "user_states": TableSchema(
                table_name=self.get_table_name("user_states"),
                columns=[
                    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "user_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "state_id", "type": "INTEGER", "mode": "REQUIRED"},
                    {"name": "created_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
                partition_field="created_date",
                clustering_fields=["user_id", "state_id"],
            ),
        }

        if table_name not in schemas:
            raise ValueError(f"Unknown table schema: {table_name}")

        return schemas[table_name]

    def execute_full_sync(self, export_data: dict[str, Any]) -> SyncResult:
        """Execute a full data synchronization (replace mode)"""
        try:
            self.initialize_client()

            if not self.test_connection():
                return SyncResult(
                    success=False,
                    records_exported=0,
                    tables_created=[],
                    tables_updated=[],
                    error_message="Connection test failed",
                    sync_timestamp=get_timezone_aware_now(),
                )

            self.create_dataset_if_not_exists()

            total_records = 0
            tables_created = []
            tables_updated = []

            for table_base_name, table_data in export_data.items():
                table_name = self.get_table_name(table_base_name)
                schema = self._get_table_schema(table_base_name)

                created = self.create_table_if_not_exists(schema)

                if table_data:
                    records_exported = self.export_data(
                        table_name, table_data, schema, mode="replace"
                    )
                    total_records += records_exported

                    # Only count tables with data as created/updated
                    if created:
                        tables_created.append(table_name)
                    else:
                        tables_updated.append(table_name)

                    # Calculate last synced ID for full sync
                    record_ids = [
                        record.get("id") for record in table_data if record.get("id")
                    ]
                    max_id = max(record_ids) if record_ids else None
                    self.update_sync_metadata(
                        table_name, get_timezone_aware_now(), max_id
                    )
                elif created:
                    # Table was created but has no data
                    tables_created.append(table_name)
                    self.update_sync_metadata(
                        table_name, get_timezone_aware_now(), None
                    )
                else:
                    # Table exists but has no data - don't count as created or updated
                    self.update_sync_metadata(
                        table_name, get_timezone_aware_now(), None
                    )

            return SyncResult(
                success=True,
                records_exported=total_records,
                tables_created=tables_created,
                tables_updated=tables_updated,
                sync_timestamp=get_timezone_aware_now(),
            )

        except Exception as e:
            return SyncResult(
                success=False,
                records_exported=0,
                tables_created=[],
                tables_updated=[],
                error_message=str(e),
                sync_timestamp=get_timezone_aware_now(),
            )

    def execute_incremental_sync(
        self, export_data: dict[str, Any], last_sync: datetime | None = None
    ) -> SyncResult:
        """Execute an incremental data synchronization (append mode)"""
        try:
            self.initialize_client()

            if not self.test_connection():
                return SyncResult(
                    success=False,
                    records_exported=0,
                    tables_created=[],
                    tables_updated=[],
                    error_message="Connection test failed",
                    sync_timestamp=get_timezone_aware_now(),
                )

            self.create_dataset_if_not_exists()

            total_records = 0
            tables_created = []
            tables_updated = []

            for table_base_name, table_data in export_data.items():
                table_name = self.get_table_name(table_base_name)
                schema = self._get_table_schema(table_base_name)

                # Get per-table sync metadata (more granular than organization-level)
                last_table_sync, last_synced_id = self.get_table_sync_metadata(
                    table_name
                )
                # Only use organization-level last_sync if table has been synced before
                # For tables that have never been synced (last_table_sync is None),
                # keep it as None so all data gets synced
                if last_sync and last_table_sync and last_sync < last_table_sync:
                    last_table_sync = last_sync

                created = self.create_table_if_not_exists(schema)

                if table_data:
                    filtered_data = self._filter_incremental_data(
                        table_data, last_table_sync, last_synced_id
                    )

                    if filtered_data:
                        records_exported = self.export_data(
                            table_name, filtered_data, schema, mode="append"
                        )
                        total_records += records_exported

                        # Only count tables with data as created/updated
                        if created:
                            tables_created.append(table_name)
                        else:
                            tables_updated.append(table_name)

                        # Calculate last synced ID from the data we just exported
                        record_ids = [
                            record.get("id")
                            for record in filtered_data
                            if record.get("id") is not None
                        ]
                        max_id = max(record_ids) if record_ids else None  # type: ignore[type-var]
                        self.update_sync_metadata(
                            table_name, get_timezone_aware_now(), max_id
                        )
                    elif created:
                        # Table was created but has no data
                        tables_created.append(table_name)
                        self.update_sync_metadata(
                            table_name, get_timezone_aware_now(), last_synced_id
                        )
                    else:
                        # Update timestamp even if no new data (to track sync attempts)
                        self.update_sync_metadata(
                            table_name, get_timezone_aware_now(), last_synced_id
                        )
                elif created:
                    # Table was created but has no data at all
                    tables_created.append(table_name)
                    self.update_sync_metadata(
                        table_name, get_timezone_aware_now(), last_synced_id
                    )
                else:
                    # Update timestamp even if no data (to track sync attempts)
                    self.update_sync_metadata(
                        table_name, get_timezone_aware_now(), last_synced_id
                    )

            return SyncResult(
                success=True,
                records_exported=total_records,
                tables_created=tables_created,
                tables_updated=tables_updated,
                sync_timestamp=get_timezone_aware_now(),
            )

        except Exception as e:
            return SyncResult(
                success=False,
                records_exported=0,
                tables_created=[],
                tables_updated=[],
                error_message=str(e),
                sync_timestamp=get_timezone_aware_now(),
            )

    def _filter_incremental_data(
        self,
        data: list[dict[str, Any]],
        last_sync: datetime | None,
        last_synced_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Filter data for incremental sync based on timestamp and ID"""
        if not last_sync:
            return data

        filtered_data = []
        for record in data:
            record_timestamp = None
            record_id = record.get("id")

            # Extract timestamp from record
            for field in ["modified_date", "created_date", "updated_at", "created_at"]:
                if field in record and record[field]:
                    if isinstance(record[field], datetime):
                        record_timestamp = record[field]
                    elif isinstance(record[field], str):
                        try:
                            record_timestamp = datetime.fromisoformat(
                                record[field].replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            continue
                    break

            # Skip records without timestamps (they can't be reliably synced incrementally)
            if not record_timestamp:
                continue

            # Normalize timezones for comparison - convert both to naive UTC
            if last_sync.tzinfo is not None:
                # Convert timezone-aware last_sync to naive UTC
                last_sync_normalized = last_sync.astimezone(timezone.utc).replace(
                    tzinfo=None
                )
            else:
                last_sync_normalized = last_sync

            if record_timestamp.tzinfo is not None:
                # Convert timezone-aware record_timestamp to naive UTC
                record_timestamp_normalized = record_timestamp.astimezone(
                    timezone.utc
                ).replace(tzinfo=None)
            else:
                record_timestamp_normalized = record_timestamp

            # Include records newer than last sync
            if record_timestamp_normalized > last_sync_normalized:
                filtered_data.append(record)
            # For records with same timestamp as last sync, use ID tiebreaking
            elif (
                record_timestamp_normalized == last_sync_normalized
                and last_synced_id
                and record_id
                and record_id > last_synced_id
            ):
                filtered_data.append(record)

        return filtered_data
