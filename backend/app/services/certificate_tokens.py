from typing import Any

from sqlmodel import Session, col, select

from app.models.entity import Entity
from app.models.form import FormField, FormFieldType
from app.models.location import Block, District, State

# Fixed tokens that are always available (independent of form fields)
FIXED_TOKENS: list[dict[str, str]] = [
    {"token": "test_name", "label": "Test Name"},
    {"token": "completion_date", "label": "Completion Date"},
    {"token": "score", "label": "Score"},
]


def get_available_tokens(form_id: int | None, session: Session) -> list[dict[str, str]]:
    """
    Get all available certificate tokens.

    Returns fixed tokens plus dynamic tokens from form fields if a form is specified.

    Args:
        form_id: Optional form ID to get dynamic tokens from
        session: Database session

    Returns:
        List of token dictionaries with token and label
    """
    tokens = [token.copy() for token in FIXED_TOKENS]

    if form_id:
        form_fields = session.exec(
            select(FormField)
            .where(FormField.form_id == form_id)
            .order_by(col(FormField.order))
        ).all()

        for field in form_fields:
            tokens.append(
                {
                    "token": field.name,
                    "label": field.label,
                }
            )

    return tokens


def resolve_form_response_values(
    form_id: int,
    responses: dict[str, Any],
    session: Session,
) -> dict[str, Any]:
    """
    Resolve raw form response values to human-readable labels for certificate tokens.

    For entity/location fields, resolves IDs to names.
    For select/radio fields, resolves option values to labels.
    For multi_select fields, resolves values to comma-joined labels.
    Other field types are passed through unchanged.
    """
    if not responses:
        return {}

    # Fetch form fields to determine field types
    form_fields = session.exec(
        select(FormField).where(FormField.form_id == form_id)
    ).all()

    field_map: dict[str, FormField] = {field.name: field for field in form_fields}

    # Collect IDs to resolve, grouped by model type
    id_field_types = {
        FormFieldType.ENTITY: set[int](),
        FormFieldType.STATE: set[int](),
        FormFieldType.DISTRICT: set[int](),
        FormFieldType.BLOCK: set[int](),
    }

    for field_name, value in responses.items():
        field = field_map.get(field_name)
        if not field:
            continue
        id_set = id_field_types.get(field.field_type)
        if id_set is not None:
            try:
                id_set.add(int(value))
            except (TypeError, ValueError):
                pass

    # Batch-fetch names (one query per model type that has IDs)
    model_map = {
        FormFieldType.ENTITY: Entity,
        FormFieldType.STATE: State,
        FormFieldType.DISTRICT: District,
        FormFieldType.BLOCK: Block,
    }

    name_lookups: dict[FormFieldType, dict[int, str]] = {}
    for field_type, ids in id_field_types.items():
        if not ids:
            continue
        model = model_map[field_type]
        rows = session.exec(
            select(model.id, model.name).where(col(model.id).in_(ids))  # type: ignore[attr-defined]
        ).all()
        name_lookups[field_type] = {row[0]: row[1] for row in rows}

    # Build resolved dict
    resolved: dict[str, Any] = {}
    for field_name, value in responses.items():
        field = field_map.get(field_name)
        if not field:
            resolved[field_name] = value
            continue

        # Entity/location fields: resolve ID to name
        lookup = name_lookups.get(field.field_type)
        if lookup is not None:
            try:
                resolved[field_name] = lookup.get(int(value), "")
            except (TypeError, ValueError):
                resolved[field_name] = value
        # Select/radio: resolve option value to label
        elif field.field_type in (FormFieldType.SELECT, FormFieldType.RADIO):
            if value and field.options:
                option_map = {opt["value"]: opt["label"] for opt in field.options}
                resolved[field_name] = option_map.get(value, value)
            else:
                resolved[field_name] = value
        # Multi-select: resolve values to comma-joined labels
        elif field.field_type == FormFieldType.MULTI_SELECT:
            if isinstance(value, list) and field.options:
                option_map = {opt["value"]: opt["label"] for opt in field.options}
                resolved[field_name] = ", ".join(
                    str(option_map.get(v, v)) for v in value
                )
            else:
                resolved[field_name] = value
        else:
            resolved[field_name] = value

    return resolved
