from sqlmodel import Field, SQLModel


# JSON payload containing access token and refresh token
class Token(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # expiry time in seconds


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class RefreshTokenRequest(SQLModel):
    refresh_token: str


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
