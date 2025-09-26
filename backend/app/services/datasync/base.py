from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TableSchema(BaseModel):
    """Schema definition for BigQuery tables"""

    table_name: str
    columns: list[dict[str, Any]]
    partition_field: str | None = None
    clustering_fields: list[str] | None = None


class SyncResult(BaseModel):
    """Result of a data synchronization operation"""

    success: bool
    records_exported: int
    tables_created: list[str]
    tables_updated: list[str]
    error_message: str | None = None
    sync_timestamp: datetime
