# E1-07: Dane demo i instrukcja uruchomienia

**Fala:** 2 · **Zależności:** E1-02, E1-03 · **Role:** implementer (model `haiku` wystarczy) · **Wymagania:** —

## Cel
`make seed` tworzy konto demo z realistycznymi, wymyślonymi transakcjami z 3 ostatnich miesięcy; README opisuje uruchomienie demo krok po kroku.

## Przeczytaj
- `docs/csv-format.md` i `data/fixtures/csv/testbank-2026-10.csv` (styl danych)
- `src/backend/coffer/accounts/service.py` (tylko sygnatury `register`), `src/backend/coffer/transactions/models.py`
- `Makefile` (cel `seed`), `README.md`

## Pliki
- **implementer:** `src/backend/coffer/scripts/seed_demo.py`, `README.md` (sekcja „Uruchomienie demo”)

## Kontrakt
- `python -m coffer.scripts.seed_demo`: idempotentny; jeśli `demo@coffer.local` istnieje, usuwa jego transakcje i tworzy je ponownie. Hasło `demo12345`.
- Transakcje: 3 pełne miesiące wstecz od bieżącego + bieżący do dziś. Co miesiąc: wynagrodzenie ~8 500 zł (Wynagrodzenie), czynsz (Mieszkanie), rachunki, 10–20 zakupów spożywczych, transport, rozrywka, jeden przelew własny i jedna wpłata na inwestycje (kategorie spoza budżetu). Nadwyżka dodatnia w co najmniej 2 miesiącach. Kwoty `Decimal`, generator z ustalonym `random.seed(42)`.
- Opisy wymyślone, w stylu bankowym, bez prawdziwych danych osobowych.
- README: wymagania (Docker Desktop, uv, Node, Ollama + `ollama pull qwen3:8b`), kolejność: `make setup`, `make db-up`, `make migrate`, `make seed`, `make dev-api`, `make dev-web`, adres `http://localhost:5173`, dane logowania demo; jak wyłączyć AI (`COFFER_LLM_PROVIDER=none`).

## Kryteria akceptacji
- [ ] `make seed` dwukrotnie pod rząd działa bez błędu
- [ ] `make lint` przechodzi
