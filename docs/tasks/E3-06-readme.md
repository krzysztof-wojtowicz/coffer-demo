# E3-06: README: instalacja na nowej maszynie, opis działania, struktura kodu

**Fala:** E3/3 · **Zależności:** E3-01..E3-05 · **Role:** implementer · **Wymagania:** —

## Cel
Osoba z zespołu albo prowadzący klonuje repo na innym komputerze i według `README.md` uruchamia aplikację bez pytania kogokolwiek. README wyjaśnia, co działa, jak działa i gdzie co jest w kodzie.

## Przeczytaj
- obecny `README.md`, `Makefile`, `.env.example`, `compose.yaml`, `CLAUDE.md`, `docs/agents.md`, `docs/tasks/README.md`
- `docs/plan.md`: tylko sekcje 0, 1 i 4 (`grep -n "^## "` i czytaj fragmenty)
- strukturę katalogów: `find src -type d -not -path "*/node_modules*" -not -path "*/.venv*" -not -path "*__pycache__*"`
- `src/backend/coffer/core/config.py`, `src/backend/coffer/agent/prompts/surplus_v2.md`

## Pliki
- **implementer:** `README.md`

## Kontrakt (sekcje README, po polsku)
1. **Coffer w skrócie:** 3–4 zdania + lista funkcji, które działają (konto, transakcje, import CSV, analiza miesiąca, profil, asystent AI z historią i śladem), i czego jeszcze nie ma (portfel, kursy NBP, edycja transakcji, wyszukiwanie informacji o spółce).
2. **Wymagania:** konkretne wersje i sposób instalacji na macOS (Homebrew) z jednym akapitem dla Linuksa/Windows (WSL2): Git, Docker Desktop (Postgres 16 w kontenerze), `uv` (sam instaluje Pythona 3.12), Node.js ≥ 20 + npm, Ollama + `ollama pull qwen3:8b` (ok. 5 GB; min. 16 GB RAM zalecane; mniejsza alternatywa `qwen3:4b` przez `COFFER_OLLAMA_MODEL`). Wolne porty: 5432, 8000, 5173, 11434.
3. **Pierwsze uruchomienie krok po kroku:** `git clone`, `cp .env.example .env` (opcjonalnie), `make setup`, `make db-up`, `make migrate`, `make seed`, w dwóch terminalach `make dev-api` i `make dev-web`, `http://localhost:5173`, konto demo. Każda komenda z jednym zdaniem „co robi”. Jak sprawdzić, że działa (`curl localhost:8000/api/health`, status modelu w panelu asystenta).
4. **Konfiguracja:** tabela wszystkich zmiennych `COFFER_*` z `config.py` (nazwa, domyślna wartość, opis). Jak wyłączyć AI, jak zmienić model.
5. **Najczęstsze problemy:** Docker nie działa; port zajęty; `ollama` nie odpowiada / model nieściągnięty (status „Model niedostępny”); wolna odpowiedź modelu; reset bazy (`make db-down`, usunięcie wolumenu, `make migrate`, `make seed`).
6. **Jak to działa:** diagram (ASCII) przeglądarka → Vite proxy → FastAPI → Postgres / Ollama; zasada „rdzeń liczy, agent interpretuje”; przebieg sugestii nadwyżki krok po kroku (narzędzia → model → walidator → poprawka → zapis → SSE) z odesłaniem do `docs/plan.md` sekcja 4; deduplikacja importu (multizbiór: data + kwota + opis po znormalizowaniu spacji); prywatność (co trafia do modelu).
7. **Struktura kodu:** drzewo katalogów z jednolinijkowym opisem każdego modułu backendu (`core`, `accounts`, `transactions`, `imports`, `budget`, `analytics`, `profile`, `agent` z podkatalogami) i frontendu (`features/*`, `components/ui`, `api`, `lib`, `i18n`), plus `docs/`, `data/fixtures`, `.claude/`. Zasady modułów (tylko `service.py` publiczny, `import-linter`).
8. **Testy i jakość:** `make check`, `make test-backend ARGS=...`, gdzie są testy, osobne bazy testowe.
9. **Praca z agentami AI:** 3–4 zdania + odesłanie do `docs/agents.md` i `docs/tasks/`.
10. **Dokumentacja:** linki do `docs/` (wizja, wymagania, słownik, UC, plan, format CSV).

Wszystkie komendy w README muszą istnieć (sprawdź w `Makefile`). Zwięźle: tabele i listy zamiast akapitów.

## Kryteria akceptacji
- [ ] każda komenda z README sprawdzona (`make -n <cel>` albo uruchomienie)
- [ ] tabela konfiguracji zgodna z `config.py`
