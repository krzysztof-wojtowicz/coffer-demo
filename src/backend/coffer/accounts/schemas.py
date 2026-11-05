import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


class Credentials(BaseModel):
    email: Annotated[str, BeforeValidator(_normalize_email), Field(max_length=254)]
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("Nieprawidłowy adres e-mail")
        return value


class UserOut(BaseModel):
    id: int
    email: str
