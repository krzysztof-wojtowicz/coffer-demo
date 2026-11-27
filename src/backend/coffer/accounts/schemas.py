import re
import unicodedata
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@(?:[^@\s.]+\.)+[^@\s.]{2,}$")


def _normalize_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


Email = Annotated[str, BeforeValidator(_normalize_email), Field(max_length=254)]
# The max length (DoS cap before hashing) is checked in api.py, not here: a pydantic error
# would echo the password back in `input`. The full policy is checked in service.
Password = Annotated[str, Field(min_length=1)]


NAME_ERROR = "Imię musi mieć od 1 do 50 znaków"


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


DisplayName = Annotated[str, BeforeValidator(_strip), Field(min_length=1, max_length=50)]


class NameChange(BaseModel):
    display_name: DisplayName

    @field_validator("display_name")
    @classmethod
    def _no_nul(cls, value: str) -> str:
        # NUL is a 500 in PostgreSQL; control/format chars (newlines, bidi) spoof the UI.
        if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in value):
            raise ValueError(NAME_ERROR)
        return value


class LoginIn(BaseModel):
    email: Email
    password: Password

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("Nieprawidłowy adres e-mail")
        return value


class RegisterIn(LoginIn, NameChange):
    pass


class PasswordChange(BaseModel):
    current_password: Password
    new_password: Password


class PasswordConfirm(BaseModel):
    password: Password


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
