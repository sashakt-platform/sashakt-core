import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


def create_token(
    user_id: str | Any, expires_delta: timedelta, token_type: str = "access"
) -> str:
    """
    Create a JWT token with the specified type and expiration

    Args:
        user_id: User ID
        expires_delta: Time until token expires
        token_type: Type of token ("access" or "refresh")
    """
    # JWT expires should remain in UTC for standards compliance
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "exp": expire,
        "sub": str(user_id),
        "type": token_type,
        "jti": str(uuid.uuid4()),  # Unique identifier
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_access_token(user_id: str | Any, expires_delta: timedelta) -> str:
    return create_token(user_id, expires_delta, "access")


def create_refresh_token(user_id: str | Any, expires_delta: timedelta) -> str:
    return create_token(user_id, expires_delta, "refresh")


def verify_token(token: str, token_type: str = "access") -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type_in_payload: str = payload.get("type", "access")

        if user_id is None or token_type_in_payload != token_type:
            return None
        return user_id
    except jwt.PyJWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
