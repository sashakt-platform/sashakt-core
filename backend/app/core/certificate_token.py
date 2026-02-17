import uuid


def generate_certificate_token() -> str:
    """Generate a random UUID token for certificate download."""
    return str(uuid.uuid4())
