# Praca z agentami AI (Claude Code)

Jak projekt jest przygotowany do równoległej pracy wielu agentów i ludzi.

## Elementy

| Plik | Rola | Kto czyta |
|---|---|---|
| `CLAUDE.md` | Krótki, wspólny kontekst: struktura, komendy, twarde zasady. Ładuje się automatycznie każdemu agentowi. | wszyscy |
| `docs/tasks/E*-*.md` | **Karta zadania**: cel, lista plików do przeczytania, pliki na własność per rola, kontrakt, kryteria akceptacji. Jedyne źródło kontekstu dla agenta, który startuje bez wiedzy o projekcie. | implementer, tester |
| `docs/tasks/README.md` | Tablica statusu i fal. Edytuje tylko orkiestrator. | orkiestrator, ludzie |
| `.claude/agents/*.md` | **Drużyna**: 16 nazwanych agentów (postacie z Władcy Pierścieni). Każdy ma osobowość, domyślną rolę, model i narzędzia. | Claude Code |
| `.claude/roles/*.md` | Role do przydziału na zadanie (`Rola: <nazwa>` w prompcie) i `_zasady.md` wspólne dla wszystkich. | agenci |
| `.claude/skills/druzyna/` | Orkiestracja Drużyny: skład, przydział po imionach, nadpisywanie ról i modeli, limit 3 agentów naraz, przekazywanie uwag, wznawianie. | sesja główna |
| `.claude/skills/run-task/` | Realizacja kart z `docs/tasks/`: wybór kart, implementer + tester równolegle, integracja, rundy poprawek. | sesja główna |

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
- Modele: `opus` dla architektury, recenzji i bezpieczeństwa, `sonnet` dla implementacji i testów, `haiku` dla zwiadu i drobnych poprawek (domyślne w definicjach agentów, nadpisywalne na zadanie).
- Recenzja (`elrond`) raz na falę, nie na każdą kartę.
- Maks. 3 agentów naraz: więcej szybko wyczerpuje limit użycia API.

## Jak uruchomić
W sesji Claude Code w katalogu repo: „zrealizuj falę 1 z `docs/tasks`” albo `/run-task E1-03`. Pracę można też przydzielać po imionach:

- „Aragorn i Samwise robią limity doradcy” (domyślne role: backend + tester),
- „Gimli robi testy migracji” (zmiana roli na zadanie),
- „niech Galadriela przejrzy auth, a Merry sprawdzi, gdzie liczymy sumy”,
- „Bard, znajdź i napraw luki w imporcie” (luka → test-exploit → poprawka → zielony test),
- „wszyscy na Haiku” (nadpisanie modelu).

| Agent | Domyślna rola | Model |
|---|---|---|
| gandalf | architekt, triage | opus |
| elrond | recenzent (tylko odczyt) | opus |
| galadriel | bezpieczeństwo (tylko odczyt) | opus |
| treebeard | projektant modelu danych | opus |
| aragorn | implementer backendu | sonnet |
| legolas | implementer frontendu | sonnet |
| gimli | migracje | sonnet |
| eowyn | AI/LLM | sonnet |
| samwise | tester | sonnet |
| boromir | odporność, red team lokalnie | sonnet |
| bard | łowca luk: znajdź, udowodnij testem, napraw | opus |
| frodo | strażnik wdrożenia | sonnet |
| faramir | CI/CD, DevOps | sonnet |
| bilbo | dokumentacja | sonnet |
| merry | zwiadowca (tylko odczyt) | haiku |
| pippin | drobne poprawki | haiku | Nowe zadanie: skopiuj `docs/tasks/_template.md`, uzupełnij kontrakt i dodaj wiersz do `docs/tasks/README.md`.

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
