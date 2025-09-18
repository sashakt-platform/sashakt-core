"""
Generic sorting utilities for API endpoints.
This module provides a standardized way to handle sorting across all API endpoints
"""

from enum import Enum
from typing import Any

from fastapi import HTTPException, Query
from sqlalchemy import Column
from sqlalchemy.orm import InstrumentedAttribute


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SortingParams:
    def __init__(
        self,
        sort_by: str | None = None,
        sort_order: SortOrder = SortOrder.ASC,
    ):
        self.sort_by = sort_by
        self.sort_order = sort_order

    def apply_default_if_none(
        self, default_field: str, default_order: SortOrder = SortOrder.DESC
    ) -> "SortingParams":
        """Apply default sorting if no sorting was specified"""
        if self.sort_by is None:
            return SortingParams(sort_by=default_field, sort_order=default_order)
        return self

    def apply_to_query(
        self,
        query: Any,
        sort_config: dict[str, InstrumentedAttribute | Column],
    ) -> Any:
        """
        Apply sorting to a SQLModel query based on the sort configuration.

        Args:
            query: The SQLModel select query to apply sorting to
            sort_config: Dictionary mapping API field names to database columns/attributes

        Returns:
            Modified query with sorting applied

        Raises:
            HTTPException: If sort_by field is not allowed or invalid
        """
        if not self.sort_by:
            return query

        if self.sort_by not in sort_config:
            allowed_fields = list(sort_config.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort field '{self.sort_by}'. Allowed fields: {allowed_fields}",
            )

        sort_column = sort_config[self.sort_by]

        # handle relationship fields that require joins
        if hasattr(sort_column, "property") and hasattr(sort_column.property, "mapper"):
            related_model = sort_column.property.mapper.class_
            query = query.outerjoin(related_model)

        # apply sorting
        if self.sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        return query

    def is_sorting_requested(self) -> bool:
        """Check if sorting was requested"""
        return self.sort_by is not None


def create_sorting_dependency(sort_config: dict[str, Any]) -> Any:
    """
    Create a FastAPI dependency for sorting with validation.

    Args:
        sort_config: Dictionary mapping API field names to database columns

    Returns:
        FastAPI dependency function
    """
    allowed_fields = list(sort_config.keys())

    def get_sorting_params(
        sort_by: str | None = Query(
            None,
            description=f"Field to sort by. Allowed values: {allowed_fields}",
            alias="sort_by",
        ),
        sort_order: SortOrder = Query(
            SortOrder.ASC,
            description="Sort order: 'asc' for ascending, 'desc' for descending",
            alias="sort_order",
        ),
    ) -> SortingParams:
        return SortingParams(sort_by=sort_by, sort_order=sort_order)

    return get_sorting_params


def validate_sort_field(field_name: str, allowed_fields: list[str]) -> None:
    """Validate that a sort field is in the allowed list"""
    if field_name and field_name not in allowed_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort field '{field_name}'. Allowed fields: {allowed_fields}",
        )


def get_sort_column(
    field_name: str, sort_config: dict[str, InstrumentedAttribute | Column]
) -> InstrumentedAttribute | Column | None:
    """Get the database column for a sort field"""
    return sort_config.get(field_name)
