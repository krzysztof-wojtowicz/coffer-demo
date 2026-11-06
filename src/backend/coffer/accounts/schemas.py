import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@(?:[^@\s.]+\.)+[^@\s.]{2,}$")


def _normalize_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


Email = Annotated[str, BeforeValidator(_normalize_email), Field(max_length=254)]
# The max length (DoS cap before hashing) is checked in api.py, not here: a pydantic error
# would echo the password back in `input`. The full policy is checked in service.
Password = Annotated[str, Field(min_length=1)]


class Credentials(BaseModel):
    email: Email
    password: Password

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("Nieprawidłowy adres e-mail")
        return value


class PasswordChange(BaseModel):
    current_password: Password
    new_password: Password


class PasswordConfirm(BaseModel):
    password: Password


class UserOut(BaseModel):
    id: int
    email: str
