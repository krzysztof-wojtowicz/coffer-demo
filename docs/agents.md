# Praca z agentami AI (Claude Code)

Jak projekt jest przygotowany do równoległej pracy wielu agentów i ludzi.

## Elementy

| Plik | Rola | Kto czyta |
|---|---|---|
| `CLAUDE.md` | Krótki, wspólny kontekst: struktura, komendy, twarde zasady. Ładuje się automatycznie każdemu agentowi. | wszyscy |
| `docs/tasks/E*-*.md` | **Karta zadania**: cel, lista plików do przeczytania, pliki na własność per rola, kontrakt, kryteria akceptacji. Jedyne źródło kontekstu dla agenta, który startuje bez wiedzy o projekcie. | implementer, tester |
| `docs/tasks/README.md` | Tablica statusu i fal. Edytuje tylko orkiestrator. | orkiestrator, ludzie |
| `.claude/agents/*.md` | Role: `implementer`, `tester`, `reviewer`, `spec-writer` (narzędzia, model, zasady). | Claude Code |
| `.claude/skills/run-task/` | Procedura orkiestracji: wybór kart, równoległe uruchomienie, integracja, rundy poprawek. | sesja główna |

## Zasady, które pozwalają pracować równolegle
1. **Rozłączne pliki:** karty jednej fali nie dzielą plików. Wspólne fundamenty (modele, fikstury, konfiguracja) powstają wcześniej, w fali 0.
2. **Kontrakt przed kodem:** sygnatury, endpointy, kody błędów i modele są w karcie, zanim ktokolwiek zacznie pisać. Implementer i tester pracują równolegle z tego samego kontraktu.
3. **Tester nie czyta implementacji.** Testy wynikają z kontraktu i UC, więc nie powielają błędów ani halucynacji implementera. Implementer nie zmienia testów; rozbieżność rozstrzyga orkiestrator według kontraktu.
4. **Osobne bazy testowe:** `COFFER_TEST_DB=coffer_test_<moduł>`, więc równoległe testy nie kasują sobie danych.
5. **Fale:** fala N+1 startuje, gdy fala N ma status `done` i `make check` przechodzi.

## Ekonomia tokenów
- `CLAUDE.md` jest krótki, bo ładuje się każdemu agentowi. Szczegóły są w kartach, czytane tylko przez tego, kto ich potrzebuje.
- Karta wskazuje konkretne pliki do przeczytania; agent nie przegląda repo ani całego `plan.md`.
- Raporty agentów maks. ~15 linii, bez kodu. Orkiestrator nie czyta kodu, gdy testy i lint przechodzą.
- Poprawki przez kontynuację istniejącego agenta (zachowuje kontekst), nie przez nowego.
- Modele: `sonnet` dla implementacji i testów, `haiku` dla prostych zadań (dane demo, dokumentacja).
- Recenzja (`reviewer`) raz na falę, nie na każdą kartę.

## Jak uruchomić
W sesji Claude Code w katalogu repo: „zrealizuj falę 1 z `docs/tasks`” albo `/run-task E1-03`. Nowe zadanie: skopiuj `docs/tasks/_template.md`, uzupełnij kontrakt i dodaj wiersz do `docs/tasks/README.md`.

Dla 4 osób: każda osoba prowadzi własną sesję-orkiestratora na swoich kartach, na osobnej gałęzi (albo `git worktree`), z PR do `main`.

## Proponowane ustawienia projektu (do dodania ręcznie)

Agent nie może sam zmieniać swoich uprawnień, więc ten plik trzeba dodać ręcznie jako `.claude/settings.json`. Lista dozwolonych komend sprawia, że agenci w tle nie zatrzymują się na pytaniach o zgodę. Hook formatuje pliki Pythona po każdej edycji, więc agenci nie tracą tokenów na poprawki stylu.

```json
{
  "permissions": {
    "allow": [
      "Bash(make:*)", "Bash(uv run:*)", "Bash(uv sync:*)", "Bash(uv add:*)",
      "Bash(npm run:*)", "Bash(npm install:*)", "Bash(docker compose:*)",
      "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
      "Bash(curl -s http://localhost:*)"
    ],
    "deny": ["Read(./.env)", "Bash(git push:*)"]
  },
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{ "type": "command",
        "command": "f=$(jq -r '.tool_input.file_path // empty'); case \"$f\" in */src/backend/*.py) cd \"$CLAUDE_PROJECT_DIR/src/backend\" && uv run --quiet ruff format --quiet \"$f\";; esac; exit 0" }]
    }]
  }
}
```
