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


def test_incremental_export_merges_instead_of_appending() -> None:
    """An edited row must replace its copy, not add a second one.

    Most tables filter on `modified_date > last_sync`, so every edit re-sends
    the row. Appending stored one copy per edit: prod had user id=68 eighteen
    times, and candidate_test 32806 twice (mid-attempt and submitted), which
    made any count of attempts wrong.
    """
    service, client = _service_with_mock_client()

    service.export_data(
        "question_sets", [{"id": 1, "title": "Physics"}], SCHEMA, mode="append"
    )

    # The rows land in a staging table, then a MERGE keyed on id folds them in.
    staging_name = client.dataset.return_value.table.call_args[0][0]
    assert staging_name.startswith("_merge_question_sets_")

    merge_sql = client.query.call_args[0][0]
    assert "MERGE" in merge_sql
    assert "ON T.`id` = S.`id`" in merge_sql
    assert "WHEN MATCHED THEN UPDATE SET" in merge_sql
    assert "T.`title` = S.`title`" in merge_sql
    # id identifies the row; overwriting it with itself is noise.
    assert "T.`id` = S.`id`," not in merge_sql


def test_merge_collapses_repeated_ids_within_one_batch() -> None:
    """Two edits to one row in a single batch must not break the MERGE.

    BigQuery rejects a MERGE whose source matches a target row more than once
    ("UPDATE/MERGE must match at most one source row").
    """
    service, client = _service_with_mock_client()

    service.export_data(
        "question_sets",
        [{"id": 1, "title": "first"}, {"id": 1, "title": "second"}],
        SCHEMA,
        mode="append",
    )

    merge_sql = client.query.call_args[0][0]
    assert "ROW_NUMBER() OVER" in merge_sql
    assert "PARTITION BY `id`" in merge_sql


def test_merge_drops_the_staging_table() -> None:
    """The staging table must not survive the run, even if the MERGE fails."""
    service, client = _service_with_mock_client()
    client.query.side_effect = RuntimeError("merge blew up")

    exported = service.export_data(
        "question_sets", [{"id": 1, "title": "Physics"}], SCHEMA, mode="append"
    )

    # A failed merge reports 0 so the caller leaves the watermark alone.
    assert exported == 0
    client.delete_table.assert_called_once()


def test_full_sync_still_truncates_without_merging() -> None:
    """A full sync replaces the table, so it needs no staging round-trip."""
    service, client = _service_with_mock_client()

    service.export_data(
        "question_sets", [{"id": 1, "title": "Physics"}], SCHEMA, mode="replace"
    )

    target_name = client.dataset.return_value.table.call_args[0][0]
    assert target_name == "question_sets"
    client.query.assert_not_called()
