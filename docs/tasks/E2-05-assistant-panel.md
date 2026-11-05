# E2-05: Frontend: panel asystenta AI

**Fala:** E2/2 · **Zależności:** E2-02, E2-04 · **Role:** implementer + tester · **UC / wymagania:** UC-12, F31, F32, F33, N03, N08

## Cel
Użytkownik rozumie, co zrobi asystent, zanim go uruchomi: jakie dane trafią do modelu, czy model jest dostępny, ile to potrwa. Wynik jest czytelny i odróżnia się od twardych wyliczeń.

## Przeczytaj
- `docs/use-cases/UC-12-surplus-suggestion.md`
- `src/frontend/src/features/assistant/*`, `src/frontend/src/components/ui/*.tsx` (tylko propsy), `src/frontend/src/i18n/pl.ts`
- typy: `grep -n "agent" src/frontend/src/api/schema.d.ts`

## Pliki
- **implementer:** `src/frontend/src/features/assistant/**` (bez `*.test.tsx`), `src/frontend/src/i18n/pl.ts` (tylko sekcja `assistant`), `src/frontend/src/features/budget/SummaryPage.tsx` (tylko osadzenie panelu)
- **tester:** `src/frontend/src/features/assistant/*.test.tsx`

## Kontrakt
`AssistantPanel({ month: string, summary: MonthSummaryOut })`, w `Card` o tytule „Asystent AI”, obok/pod podsumowaniem.

Stany (komponent wyświetla dokładnie jeden):
1. **`idle`:**
   - Opis: „Asystent przeanalizuje podsumowanie miesiąca i zaproponuje, jak wykorzystać nadwyżkę.”
   - Status modelu z `GET /api/agent/status`: `Badge` „qwen3:8b · dostępny” (success), „Model niedostępny” (warning), „AI wyłączone” (neutral, `provider=none`).
   - Rozwijana sekcja „Jakie dane trafiają do modelu?” (`<details>`): lista z miesiącem, przychodami, wydatkami, nadwyżką i wydatkami per kategoria, wyświetlonymi z `summary`, oraz zdanie „Nie wysyłamy opisów transakcji, e-maila ani innych danych osobowych. Model działa lokalnie na tym komputerze.”
   - Przycisk „Zaproponuj, jak wykorzystać nadwyżkę”. Gdy `summary.surplus === "0.00"`: przycisk wyłączony + wyjaśnienie „W tym miesiącu nie ma nadwyżki, więc nie ma czego rozdysponować.” (bez wywołania API). Gdy model niedostępny: przycisk aktywny (status może być nieaktualny), ale z podpowiedzią.
2. **`loading`:** `Spinner`, „Asystent analizuje dane…”, licznik sekund od startu („12 s”), informacja „Model lokalny odpowiada zwykle w 10–30 s”. Przycisk „Anuluj” przerywa żądanie (`AbortController`) i wraca do `idle`.
3. **`ok`:** wyróżniona karta sugestii: `summary` jako akapit, `rationale` jako lista „Dlaczego:”, ramka z `disclaimer` (ikonka informacji, tło ostrzegawcze), stopka „Wygenerowano przez {model} w {duration_ms/1000 zaokrąglone do 0,1} s · {godzina}”. Przyciski „Wygeneruj ponownie” i „Wyczyść”.
4. **`unavailable`:** komunikat „Asystent AI jest chwilowo niedostępny. Wyliczenia powyżej są aktualne.” + „Spróbuj ponownie”. Ten sam stan dla błędu sieci/HTTP.
5. **`no_surplus`:** (gdy API tak odpowie) jak w punkcie 1 dla nadwyżki 0.

- Zmiana `month` resetuje panel do `idle` i przerywa trwające żądanie.
- Logika stanów w czystej funkcji/reducerze `assistantReducer` w `assistant/state.ts` (eksportowane typy akcji: `start`, `success(response)`, `failure`, `cancel`, `reset`), żeby dało się ją testować bez renderu.

### Testy (tester)
- `assistantReducer`: przejścia `idle → loading → ok/unavailable/no_surplus`, `cancel` i `reset` → `idle`.
- Render (Testing Library, `fetch` zamockowany przez `vi.stubGlobal`): przycisk wyłączony przy `surplus "0.00"`; po kliknięciu stan ładowania; odpowiedź `ok` pokazuje `summary`, punkty `rationale` i `disclaimer`; odpowiedź `unavailable` pokazuje komunikat; sekcja danych zawiera kwoty z `summary`.

## Kryteria akceptacji
- [ ] `make check-web` przechodzi (z testami testera)
- [ ] ręcznie z Ollamą: pełny przebieg idle → loading (licznik) → ok
