"""Password policy (UC-01 step 4).

The same rules live in the frontend: src/frontend/src/features/auth/password.ts.
"""

from functools import lru_cache
from pathlib import Path

MIN_LENGTH = 12
# Upper bound against hashing DoS; Argon2 cost does not depend much on input size, but we
# still refuse megabyte-long "passwords" before they reach the hasher.
MAX_LENGTH = 128
MIN_DISTINCT_CHARS = 5

# Explicit whitespace set for trimming, identical to WHITESPACE in password.ts (Python's
# str.strip() and JS trim() differ: U+FEFF, U+001C-001F, U+0085). Equals str.isspace().
WHITESPACE = (
    "\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f \x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)

_COMMON_FILE = Path(__file__).with_name("common_passwords.txt")


@lru_cache
def common_passwords() -> frozenset[str]:
    lines = _COMMON_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line and not line.startswith("#"))


def password_problems(password: str, email: str) -> list[str]:
    """Return the Polish descriptions of the rules the password breaks (empty = OK)."""
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Hasło musi mieć co najmniej {MIN_LENGTH} znaków.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Hasło może mieć najwyżej {MAX_LENGTH} znaków.")
    if len(set(password)) < MIN_DISTINCT_CHARS:
        problems.append(f"Hasło musi zawierać co najmniej {MIN_DISTINCT_CHARS} różnych znaków.")
    lowered = password.strip(WHITESPACE).lower()
    email = email.strip(WHITESPACE).lower()
    if lowered and lowered in {email, email.split("@", 1)[0]}:
        problems.append("Hasło nie może być takie samo jak adres e-mail.")
    if lowered in common_passwords():
        problems.append("To hasło jest zbyt popularne. Wybierz inne.")
    return problems
