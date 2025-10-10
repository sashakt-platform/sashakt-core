"""
Sort field configurations for all models.

This module defines which fields can be sorted for each model and maps
API field names to actual database columns/relationships.
"""

from typing import Any

from app.models import (
    Entity,
    EntityType,
    Question,
    QuestionRevision,
    Tag,
    TagType,
    Test,
    User,
)
from app.models.role import Role

# User sorting configuration
UserSortConfig: Any = {
    "full_name": User.full_name,
    "email": User.email,
    "phone": User.phone,
    "created_date": User.created_date,
    "modified_date": User.modified_date,
    "is_active": User.is_active,
    "role_label": (User.role, Role.label),
}


# Question sorting configuration
QuestionSortConfig: Any = {
    "created_date": Question.created_date,
    "modified_date": Question.modified_date,
    "is_active": Question.is_active,
    "question_text": QuestionRevision.question_text,
}


# Test sorting configuration
TestSortConfig: Any = {
    "name": Test.name,
    "created_date": Test.created_date,
    "modified_date": Test.modified_date,
    "is_active": Test.is_active,
}


# Tag sorting configuration
TagSortConfig: Any = {
    "name": Tag.name,
    "created_date": Tag.created_date,
    "modified_date": Tag.modified_date,
    "is_active": Tag.is_active,
    "tag_type_name": (Tag.tag_type, TagType.name),
}


# TagType sorting configuration
TagTypeSortConfig: Any = {
    "name": TagType.name,
    "created_date": TagType.created_date,
    "modified_date": TagType.modified_date,
    "is_active": TagType.is_active,
}


# Entity sorting configuration
EntitySortConfig: Any = {
    "name": Entity.name,
    "description": Entity.description,
    "created_date": Entity.created_date,
    "modified_date": Entity.modified_date,
    "entity_type_name": (Entity.entity_type, EntityType.name),
}


# Export all configurations for easy import
ALL_SORT_CONFIGS = {
    "User": UserSortConfig,
    "Question": QuestionSortConfig,
    "Test": TestSortConfig,
    "Tag": TagSortConfig,
    "TagType": TagTypeSortConfig,
    "Entity": EntitySortConfig,
}


def get_sort_config(model_name: str) -> Any:
    """Get sort configuration for a model by name"""
    return ALL_SORT_CONFIGS.get(model_name)


def get_sortable_fields(model_name: str) -> list[str]:
    """Get list of sortable field names for a model"""
    config = get_sort_config(model_name)
    return list(config.keys()) if config else []
