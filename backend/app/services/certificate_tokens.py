from sqlmodel import Session, select

from app.models.form import FormField

# Fixed tokens that are always available (independent of form fields)
FIXED_TOKENS = [
    {"token": "test_name", "label": "Test Name"},
    {"token": "completion_date", "label": "Completion Date"},
    {"token": "score", "label": "Score"},
]


def get_available_tokens(form_id: int | None, session: Session) -> list[dict]:
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
            .order_by(FormField.order)
        ).all()

        for field in form_fields:
            tokens.append(
                {
                    "token": field.name,
                    "label": field.label,
                }
            )

    return tokens
