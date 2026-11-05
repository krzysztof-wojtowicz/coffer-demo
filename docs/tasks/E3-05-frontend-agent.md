# E3-05: Frontend: profil, asystent z postępem na żywo, historia sugestii, ślad agenta

**Fala:** E3/2 · **Zależności:** E3-01, E3-03, E3-04 · **Role:** implementer + tester · **UC / wymagania:** UC-05, UC-12, F30–F33, N06, N08

## Cel
Użytkownik uzupełnia profil, widzi postęp pracy asystenta krok po kroku, uzasadnienie z odwołaniami do danych, historię sugestii i (dla celów dydaktycznych) ślad przebiegu agenta: prompt, wywołania narzędzi, surową odpowiedź i błędy walidacji.

## Przeczytaj
- `docs/use-cases/UC-05-investment-profile.md`, `docs/use-cases/UC-12-surplus-suggestion.md`
- sekcje „Kontrakt” w `docs/tasks/E3-01-profile.md` i `docs/tasks/E3-03-surplus-workflow.md`
- `src/frontend/src/features/assistant/*`, `src/frontend/src/components/ui/*.tsx` (propsy), `src/frontend/src/App.tsx`, `src/frontend/src/components/Layout.tsx`, `src/frontend/src/i18n/pl.ts`
- typy: `grep -n "Profile\|Suggestion\|AgentRun" src/frontend/src/api/schema.d.ts`

## Pliki
- **implementer:** `src/frontend/src/features/{profile,assistant}/**` (bez `*.test.*`), `App.tsx`, `components/Layout.tsx` (nawigacja), `i18n/pl.ts` (sekcje `profile`, `assistant`, `nav`)
- **tester:** `src/frontend/src/features/assistant/*.test.ts(x)`, `src/frontend/src/features/profile/*.test.tsx`

## Kontrakt
- **`/profile`:** formularz: horyzont (radio: krótki do 2 lat / średni 2–5 lat / długi powyżej 5 lat), tolerancja ryzyka (radio: niska / średnia / wysoka z jednozdaniowym opisem), preferowane klasy (checkboxy 7 klas z polskimi nazwami, min. 1). „Zapisz profil” (`PUT`), komunikat sukcesu, błędy 422 po polsku. Informacja z UC-05: zmiana profilu nie zmienia już otrzymanych sugestii. Nawigacja: „Profil”.
- **Panel asystenta** (rozbudowa E2-05, zachowaj istniejące stany i testy, dostosuj do nowego kształtu odpowiedzi):
  - Strumień SSE: `POST /api/agent/surplus/stream` przez `fetch` + `ReadableStream` (`EventSource` nie obsługuje POST). Parser SSE w `assistant/sse.ts`: `parseSse(chunk: string, buffer: string) -> { events: {event, data}[], rest: string }` (zdarzenia rozdzielone pustą linią; dane mogą przyjść w kawałkach).
  - W `loading`: lista kroków z eventów `status` (poprzednie ze znaczkiem ✓, bieżący ze spinnerem) + licznik sekund. Event `summary` niczego nie zmienia w kafelkach (są z osobnego zapytania).
  - `ok`: `summary`; „Dlaczego:” jako lista punktów `claim` z `Badge` źródła (Budżet / Profil / Portfel) i wartością `value`; „Ryzyka:” (jeśli są); zastrzeżenie; stopka (model, czas, „z profilem” / „bez profilu”, link „Pokaż ślad agenta” → `/assistant/runs/{run_id}`). Gdy `profile_used=false`: zachęta „Uzupełnij profil inwestycyjny, aby sugestie były lepiej dopasowane” z linkiem do `/profile`.
  - Nowy stan `limited`: „Osiągnięto dzienny limit zapytań do asystenta. Spróbuj jutro.”
  - Reducer: akcja `progress(message)` dopisuje krok; pozostałe akcje bez zmian.
- **`/assistant`** (nawigacja „Asystent”): „Historia sugestii” z `GET /api/agent/suggestions` (karta na sugestię: data, miesiąc, `summary`, rozwijane uzasadnienie) i „Przebiegi agenta” z `GET /api/agent/runs` (tabela: data, zadanie, status jako `Badge`, model, próby, czas).
- **`/assistant/runs/:id`:** szczegóły `AgentRunOut`: nagłówek (status, model, próby, tokeny, czas), sekcje rozwijane: „Wiadomości do modelu” (`messages`, każda z rolą), „Wywołania narzędzi” (nazwa, argumenty, wynik jako sformatowany JSON w `<pre>`), „Surowe odpowiedzi modelu”, „Błędy walidacji”. To widok dla zespołu i prowadzącego: pokazuje, co dokładnie zobaczył model (N03).

### Testy (tester)
- `parseSse`: jedno zdarzenie; kilka w jednym kawałku; zdarzenie rozcięte między kawałkami; ignorowanie komentarzy `:`.
- reducer: `progress` dopisuje kroki; `success` z `limited`.
- panel (fetch zamockowany strumieniem `ReadableStream`): kroki statusu pojawiają się w kolejności; wynik pokazuje `claim`, etykiety źródeł, `value`, ryzyka; `profile_used=false` pokazuje link do profilu; `limited` pokazuje komunikat.
- profil: zapis wysyła poprawne body; przycisk zablokowany bez zaznaczonej klasy.

## Kryteria akceptacji
- [ ] `make check-web` przechodzi
- [ ] ręcznie z Ollamą: kroki pojawiają się na żywo; ślad agenta pokazuje prompt i wyniki narzędzi
