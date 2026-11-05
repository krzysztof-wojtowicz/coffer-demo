# E1-02: Konta: rejestracja, logowanie, wylogowanie

**Fala:** 1 · **Zależności:** E1-01 · **Role:** implementer + tester · **UC / wymagania:** UC-01, UC-09, F01, F02, N01, N02

## Cel
Użytkownik zakłada konto, loguje się i wylogowuje; sesja w ciasteczku HttpOnly. Wszystkie trasy chronione zwracają 401 bez sesji.

## Przeczytaj
- `docs/use-cases/UC-01-create-account.md`, `docs/use-cases/UC-09-log-in.md`
- `src/backend/coffer/accounts/{models,tokens,deps}.py` (gotowe w E1-01, nie zmieniaj)
- `src/backend/tests/conftest.py`

## Pliki
- **implementer:** `src/backend/coffer/accounts/{api,service,schemas}.py`
- **tester:** `src/backend/tests/accounts/` (w tym `test_auth_required.py`)

## Kontrakt

### Schematy (`schemas.py`)
- `Credentials { email: str, password: str }`: e-mail obcinany ze spacji i zamieniany na małe litery, musi pasować do `^[^@\s]+@[^@\s]+\.[^@\s]+$` i mieć ≤ 254 znaki; hasło 8–128 znaków. Błąd walidacji → 422 (domyślny format FastAPI).
- `UserOut { id: int, email: str }`

### Endpointy (`router` z prefiksem `/api/auth`)
| Metoda i ścieżka | Wejście | Sukces | Błędy |
|---|---|---|---|
| `POST /register` | `Credentials` | 201 `UserOut`, ustawia ciasteczko sesji (użytkownik od razu zalogowany) | 409 `{"detail": "Konto z tym adresem e-mail już istnieje"}` |
| `POST /login` | `Credentials` | 200 `UserOut`, ustawia ciasteczko | 401 `{"detail": "Nieprawidłowy e-mail lub hasło"}` (ten sam komunikat dla nieznanego e-maila i złego hasła) |
| `POST /logout` | — | 204, usuwa wiersz sesji i ciasteczko; bez sesji też 204 | — |
| `GET /me` | — | 200 `UserOut` | 401 `{"detail": "Wymagane logowanie"}` (z `deps.py`) |

Ciasteczko: nazwa `SESSION_COOKIE`, `HttpOnly`, `SameSite=Lax`, `Secure` = `settings.cookie_secure`, `Path=/`, `Max-Age` = `session_ttl_days` w sekundach.

### Serwis (`service.py`)
- `hash_password(password: str) -> str`, `verify_password(hash: str, password: str) -> bool` (argon2-cffi, `PasswordHasher`).
- `register(db, email, password) -> User` (rzuca `EmailTaken`), `authenticate(db, email, password) -> User | None`.
- `create_session(db, user) -> str` (zwraca surowy token; w bazie tylko `hash_token`), `delete_session(db, token: str) -> None`.

### Reguły
- Hasło nigdy nie jest zapisywane ani logowane jawnie (N01): w bazie tylko hash argon2.
- Wylogowanie unieważnia sesję natychmiast: stary token po `/logout` daje 401 na `/me`.
- Wygasła sesja (`expires_at` w przeszłości) → 401.

### Test N02 (`test_auth_required.py`)
Iteruje po `app.openapi()["paths"]` i dla każdej pary (ścieżka, metoda) poza `/api/health`, `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` wysyła żądanie bez ciasteczka (parametry ścieżki zastąp np. `1` lub `2026-10`) i oczekuje 401. Test ma objąć trasy dodane przez inne moduły (dlatego iteruje po OpenAPI).

Test CSRF: `POST /api/auth/login` z nagłówkiem `Origin: https://evil.example` → 403.

## Kryteria akceptacji
- [ ] `make lint` przechodzi
- [ ] testy testera przechodzą
- [ ] w tabeli `users` nie ma jawnego hasła (test sprawdza, że `password_hash != password` i zaczyna się od `$argon2`)

## Poza zakresem
Usuwanie konta (UC-08, Etap 4), limit prób logowania, potwierdzenie e-mail, odzyskiwanie hasła.
