---
name: run-task
description: Orkiestracja zadań z docs/tasks/ przez Drużynę (aragorn/legolas jako implementer, samwise jako tester, elrond jako recenzent). Używaj, gdy użytkownik prosi o realizację karty, fali albo etapu (np. "zrób falę 1", "zrealizuj E1-03").
---

# Orkiestracja zadań Coffer

Jesteś orkiestratorem. Sam nie piszesz kodu modułów: przydzielasz karty agentom, sprawdzasz wyniki i aktualizujesz `docs/tasks/README.md` (tylko Ty go edytujesz).

## 1. Wybór pracy
- Przeczytaj `docs/tasks/README.md`. Weź karty z najniższej fali, które mają status `ready`, a ich zależności są `done`.
- Karty jednej fali mają rozłączne pliki, więc mogą iść równolegle w tym samym drzewie roboczym.

## 2. Uruchomienie (równolegle, w tle)
Dla każdej karty z rolami `implementer` + `tester` uruchom **dwóch** agentów Drużyny jednocześnie (skład i zasady: `.claude/skills/druzyna/SKILL.md`):
- implementer: `aragorn` (backend) albo `legolas` (frontend); karta z backendem i frontem → obaj, z rozłącznymi plikami,
- tester: `samwise` (przy wielu kartach naraz: inny agent z `Rola: tester`, np. `boromir` albo `gimli`).

Prompt ma być krótki, bo kontekst jest w plikach:

```
Rola: implementer
Karta: docs/tasks/E1-03-transactions.md
```

- Używaj `subagent_type: <imię>`; gdy definicje Drużyny nie są załadowane, `general-purpose` z dopiskiem „Przeczytaj .claude/agents/<imię>.md i stosuj się do niego”.
- Model: z definicji agenta; `pippin`/`merry` (haiku) wystarczą dla prostych zadań (seed, dokumentacja). Maks. 3 agentów naraz.
- Nie uruchamiaj agentów dla zadań, które zrobisz szybciej sam (np. jednolinijkowa poprawka).
- Tester rusza od razu: pisze testy z kontraktu, niezależnie od kodu. To chroni przed halucynacją implementera (testy nie są dopasowane do kodu).

## 3. Integracja karty (po zakończeniu obu agentów)
1. Uruchom `COFFER_TEST_DB=coffer_test_<moduł> make test-backend ARGS="tests/<moduł>"`.
2. Testy nie przechodzą → rozstrzygnij na podstawie **kontraktu z karty**:
   - błąd implementacji → `SendMessage` do implementera z nazwami testów i skróconym błędem (bez całego logu),
   - test sprzeczny z kontraktem → `SendMessage` do testera,
   - kontrakt niejasny → popraw kartę (sekcja „Kontrakt”), potem obu agentom krótka informacja.
3. Maks. 2 rundy poprawek na kartę. Potem zatrzymaj się i zapytaj użytkownika.
4. Ustaw status karty na `done` w `docs/tasks/README.md`, dopisz 1 linię notatki (decyzje, odstępstwa).

## 4. Koniec fali
- `make check` musi przejść w całości.
- Raz na falę (nie na kartę) uruchom `elrond` (recenzent, tylko odczyt) z listą kart fali; przy zmianach w auth/sesjach/danych osobowych także `galadriel`. Znaleziska poważne → karty poprawkowe albo `SendMessage` do implementera.
- Commit tylko za zgodą użytkownika: jeden commit na falę, komunikat `E1 fala N: <karty>`.

## Ekonomia tokenów
- Nie czytaj kodu agentów, jeśli testy i lint przechodzą; czytaj tylko miejsca wskazane w raportach lub przez reviewera.
- Logi testów przycinaj (`| tail -30`).
- Kontynuuj istniejącego agenta przez `SendMessage` zamiast startować nowego: zachowuje kontekst karty.
- Nowe zadanie = nowa karta w `docs/tasks/` (szablon: `docs/tasks/_template.md`, autor: agent z `Rola: specyfikacja`, np. `bilbo`), nie długi prompt.
