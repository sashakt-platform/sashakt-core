"""
Tests for the generic sorting utility.
"""

from typing import Any

import pytest
from fastapi import HTTPException

from app.core.sorting import SortingParams, SortOrder, create_sorting_dependency

# mock sort configuration for testing
TestSortConfig: Any = {
    "name": "mock_name_column",
    "email": "mock_email_column",
    "created_date": "mock_created_date_column",
}


class TestSortingParams:
    """Test SortingParams class"""

    def test_init_defaults(self):
        """Test SortingParams initialization with defaults"""
        sorting = SortingParams()
        assert sorting.sort_by is None
        assert sorting.sort_order == SortOrder.ASC

    def test_init_with_params(self):
        """Test SortingParams initialization with parameters"""
        sorting = SortingParams(sort_by="name", sort_order=SortOrder.DESC)
        assert sorting.sort_by == "name"
        assert sorting.sort_order == SortOrder.DESC

    def test_is_sorting_requested(self):
        """Test is_sorting_requested method"""
        sorting_none = SortingParams()
        sorting_with_field = SortingParams(sort_by="name")

        assert not sorting_none.is_sorting_requested()
        assert sorting_with_field.is_sorting_requested()

    def test_apply_to_query_no_sorting(self):
        """Test apply_to_query when no sorting is requested"""
        sorting = SortingParams()
        mock_query = "mock_query"

        result_query = sorting.apply_to_query(mock_query, TestSortConfig)
        assert result_query == mock_query

    def test_apply_to_query_invalid_field(self):
        """Test apply_to_query with invalid sort field"""
        sorting = SortingParams(sort_by="invalid_field")
        mock_query = "mock_query"

        with pytest.raises(HTTPException) as exc_info:
            sorting.apply_to_query(mock_query, TestSortConfig)

        assert exc_info.value.status_code == 400
        assert "Invalid sort field 'invalid_field'" in str(exc_info.value.detail)


class TestSortOrder:
    """Test SortOrder enum"""

    def test_enum_values(self):
        """Test SortOrder enum values"""
        assert SortOrder.ASC == "asc"
        assert SortOrder.DESC == "desc"


class TestCreateSortingDependency:
    """Test create_sorting_dependency function"""

    def test_create_dependency_function(self):
        """Test that create_sorting_dependency creates a callable function"""
        dependency_func = create_sorting_dependency(TestSortConfig)
        assert callable(dependency_func)

    def test_dependency_with_valid_params(self):
        """Test dependency function with valid parameters"""
        dependency_func = create_sorting_dependency(TestSortConfig)

        # test with valid sort_by parameter
        result = dependency_func(sort_by="name", sort_order=SortOrder.ASC)
        assert isinstance(result, SortingParams)
        assert result.sort_by == "name"
        assert result.sort_order == SortOrder.ASC

    def test_dependency_with_none_params(self):
        """Test dependency function with None parameters"""
        dependency_func = create_sorting_dependency(TestSortConfig)

        result = dependency_func(sort_by=None, sort_order=SortOrder.DESC)
        assert isinstance(result, SortingParams)
        assert result.sort_by is None
        assert result.sort_order == SortOrder.DESC


if __name__ == "__main__":
    pytest.main([__file__])
