import uuid

# Fixed tokens that are always available (independent of form fields)
FIXED_TOKENS: list[dict[str, str]] = [
    {"token": "test_name", "label": "Test Name"},
    {"token": "completion_date", "label": "Completion Date"},
    {"token": "score", "label": "Score"},
]


def generate_certificate_token() -> str:
    """Generate a random UUID token for certificate download."""
    return str(uuid.uuid4())
