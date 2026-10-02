"""Tests for the BigQuery export path.

These cover how records are encoded for BigQuery and how a failed export is
reported, both of which are invisible from the sync's return value otherwise.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.datasync.base import TableSchema
from app.services.datasync.bigquery import BigQueryService

CONFIG: dict[str, Any] = {
    "project_id": "test-project",
    "dataset_id": "test_dataset_1",
}

SCHEMA = TableSchema(
    table_name="question_sets",
    columns=[
        {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "title", "type": "STRING", "mode": "NULLABLE"},
        {"name": "marking_scheme", "type": "JSON", "mode": "NULLABLE"},
    ],
    partition_field=None,
    clustering_fields=[],
)


def _service_with_mock_client() -> tuple[BigQueryService, MagicMock]:
    service = BigQueryService(organization_id=1, config=CONFIG)
    client = MagicMock()
    service._client = client
    return service, client


def test_json_column_is_exported_as_object_not_string() -> None:
    """A JSON column must receive the dict itself.

    Stringifying it stores a quoted string, and JSON_VALUE() on that returns
    NULL, which silently breaks any scoring query built on the column.
    """
    service, client = _service_with_mock_client()
    marking_scheme = {"correct": 4, "wrong": -1, "skipped": 0}

    exported = service.export_data(
        "question_sets",
        [{"id": 1, "title": "Physics", "marking_scheme": marking_scheme}],
        SCHEMA,
    )

    assert exported == 1
    rows = client.load_table_from_json.call_args[0][0]
    assert rows[0]["marking_scheme"] == marking_scheme


def test_non_schema_dict_is_still_stringified() -> None:
    """A dict aimed at a non-JSON column keeps the previous encoding."""
    service, client = _service_with_mock_client()
    schema = TableSchema(
        table_name="question_sets",
        columns=[
            {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
            {"name": "payload", "type": "STRING", "mode": "NULLABLE"},
        ],
        partition_field=None,
        clustering_fields=[],
    )

    service.export_data("question_sets", [{"id": 1, "payload": {"a": 1}}], schema)

    rows = client.load_table_from_json.call_args[0][0]
    assert rows[0]["payload"] == '{"a": 1}'


def test_full_sync_reports_failure_when_export_fails() -> None:
    """A sync whose writes all failed must not report success."""
    service, _ = _service_with_mock_client()

    with (
        patch.object(service, "test_connection", return_value=True),
        patch.object(service, "create_dataset_if_not_exists", return_value=True),
        patch.object(service, "create_table_if_not_exists", return_value=False),
        patch.object(service, "_get_table_schema", return_value=SCHEMA),
        patch.object(service, "export_data", return_value=0),
        patch.object(service, "update_sync_metadata", return_value=True),
    ):
        result = service.execute_full_sync({"question_sets": [{"id": 1}]})

    assert result.success is False
    assert result.error_message is not None
    assert "question_sets" in result.error_message
    assert result.tables_updated == []


def test_incremental_sync_keeps_watermark_when_export_fails() -> None:
    """A failed export must not advance sync metadata.

    Advancing it would make the rows that never landed invisible to every
    later incremental run.
    """
    service, _ = _service_with_mock_client()

    with (
        patch.object(service, "test_connection", return_value=True),
        patch.object(service, "create_dataset_if_not_exists", return_value=True),
        patch.object(service, "create_table_if_not_exists", return_value=False),
        patch.object(service, "_get_table_schema", return_value=SCHEMA),
        patch.object(service, "get_table_sync_metadata", return_value=(None, None)),
        patch.object(service, "_filter_incremental_data", return_value=[{"id": 1}]),
        patch.object(service, "export_data", return_value=0),
        patch.object(service, "update_sync_metadata", return_value=True) as metadata,
    ):
        result = service.execute_incremental_sync({"question_sets": [{"id": 1}]})

    assert result.success is False
    metadata.assert_not_called()


def test_candidates_schema_carries_external_identifier() -> None:
    """The Avanti-side user id must reach BigQuery.

    candidates.identity holds the anonymous QR uuid, so without this column
    there is no way to join a Sashakt attempt back to an external user.
    """
    service, _ = _service_with_mock_client()

    columns = {c["name"] for c in service._get_table_schema("candidates").columns}

    assert "external_identifier" in columns
