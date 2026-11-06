# Coffer: kontekst dla agentów

Aplikacja do finansów osobistych z asystentem AI (projekt studencki, 4 osoby). Monorepo:
`docs/` specyfikacja i plan · `docs/tasks/` karty zadań · `src/backend/` Python/FastAPI · `src/frontend/` React/TS · `data/fixtures/` dane testowe (wymyślone).

## Jak pracujesz (oszczędnie)
- Pracujesz nad **jedną kartą zadania** (`docs/tasks/E*-*.md`). Czytasz tylko pliki z sekcji „Przeczytaj” karty i te, które sam zmieniasz. **Nie czytaj całego `docs/plan.md`**: jeśli czegoś brakuje, szukaj `grep -n` i czytaj fragment.
- Zmieniasz **tylko pliki z sekcji „Pliki” karty** przypisane do Twojej roli. Inne agenty pracują równolegle w tym samym drzewie. Potrzebujesz zmiany poza swoimi plikami? Napisz to w raporcie, nie edytuj.
- Kontrakt w karcie jest źródłem prawdy. Gdy jest niejasny albo sprzeczny, wybierz najprostszą interpretację zgodną z UC i zapisz ją w raporcie.
- Raport końcowy: maks. ~15 linii (co zrobione, wynik testów, decyzje, problemy). Bez wklejania kodu.
- Nie commituj, nie zmieniaj `docs/tasks/README.md` (to robi orkiestrator).

## Komendy (z katalogu głównego)
- `make setup`: zależności · `make db-up`: Postgres w Dockerze · `make migrate`
- `make test-backend ARGS="tests/accounts"`: testy (ustaw `COFFER_TEST_DB=coffer_test_<moduł>`, żeby nie kolidować z innymi agentami)
- `make lint`: ruff + pyright + import-linter · `make check`: wszystko (lint, testy, front)
- `make openapi`: zrzut OpenAPI + typy TS · `make dev-api` / `make dev-web` · `make seed`: dane demo

## Twarde zasady
- **Pieniądze:** tylko `Decimal`, nigdy `float`; zaokrąglanie przez `coffer.core.money.quantize` (ROUND_HALF_UP). W bazie `NUMERIC(14,2)`. W JSON kwoty to stringi.
- **Sumy liczy tylko `coffer.analytics`** (czyste funkcje, bez bazy i FastAPI).
- **Granice modułów:** moduł używa innego modułu wyłącznie przez jego `service.py` (lub publiczne dataclassy `analytics`). Rdzeń nigdy nie importuje `coffer.agent` (pilnuje `import-linter`).
- **Bezpieczeństwo:** każdy endpoint poza `/api/health` i `/api/auth/{register,login,logout}` wymaga `CurrentUser`; każde zapytanie filtruje po `user_id`. Cudzy zasób → 404.
- **AI:** do LLM trafiają tylko agregaty: bez e-maila, opisów transakcji, identyfikatorów. Brak LLM nie może psuć rdzenia.
- **Język:** UI i komunikaty błędów po polsku; kod, nazwy i komentarze po angielsku.
- Moduł: `coffer/<moduł>/{api.py, service.py, models.py, schemas.py}`; router cienki, logika w `service.py`.

## Role agentów
Drużyna 16 nazwanych agentów w `.claude/agents/` (gandalf, elrond, galadriel, bard, treebeard, aragorn, legolas, gimli, eowyn, samwise, boromir, frodo, faramir, bilbo, merry, pippin). Każdy ma domyślną rolę, ale zadanie może nadać inną (`Rola: <nazwa>` z `.claude/roles/`). Zasady wspólne: `.claude/roles/_zasady.md`. Orkiestracja: `.claude/skills/druzyna/SKILL.md`; realizacja kart: `.claude/skills/run-task/SKILL.md`.
