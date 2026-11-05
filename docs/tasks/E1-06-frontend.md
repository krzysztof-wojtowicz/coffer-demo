# E1-06: Frontend: logowanie, transakcje, podsumowanie, sugestia

**Fala:** 2 · **Zależności:** E1-02..E1-05 · **Role:** implementer (weryfikacja: `make check-web` + przegląd ręczny) · **UC / wymagania:** UC-01, UC-09, UC-10, UC-11, UC-12, N06, N08

## Cel
Klikalne demo: rejestracja/logowanie, dodawanie i usuwanie transakcji, podsumowanie miesiąca i przycisk „Poproś o sugestię”.

## Przeczytaj
- `src/frontend/src/{main.tsx,App.tsx,api/client.ts,i18n/pl.ts}`, `src/frontend/vite.config.ts`
- `src/frontend/src/api/schema.d.ts` (najpierw uruchom `make openapi`; czytaj tylko potrzebne typy przez `grep`)

## Pliki
- **implementer:** `src/frontend/src/**` (poza `api/schema.d.ts`, który tylko generujesz), `src/frontend/index.html`

## Kontrakt
- Wszystkie wywołania przez typowany `openapi-fetch` (`api/client.ts`), stan serwera w TanStack Query (`features/*/queries.ts`), bez ręcznie pisanych typów odpowiedzi.
- Struktura: `src/features/{auth,transactions,budget,assistant}/`, `src/components/` (wspólne: `Layout`, `Money`, `ErrorMessage`), `src/lib/money.ts` (`formatMoney(value: string): string` przez `Intl.NumberFormat("pl-PL", {style: "currency", currency: "PLN"})`; frontend **nie liczy** sum).
- Trasy: `/login`, `/register`, `/` (podsumowanie), `/transactions`. Strażnik: `GET /api/auth/me`; 401 → przekierowanie na `/login`. Wylogowanie w nagłówku.
- `/`: wybór miesiąca (`<input type="month">`, domyślnie bieżący), kafelki: Przychody, Wydatki, Saldo, Nadwyżka; tabela wydatków per kategoria; sekcja „Asystent AI” z przyciskiem „Poproś o sugestię”: stan ładowania („Asystent analizuje…”, model lokalny może odpowiadać kilkadziesiąt sekund), wynik (`summary`, lista `rationale`, `disclaimer` wyróżniony), komunikaty dla `no_surplus` („W tym miesiącu nie ma nadwyżki”) i `unavailable` („Asystent AI jest chwilowo niedostępny. Wyliczenia powyżej są aktualne.”). Błąd asystenta nie ukrywa podsumowania (N08).
- `/transactions`: formularz (data, kwota, opis, kategoria z `GET /api/categories`, domyślnie „Inne”), błędy walidacji 422 pokazane po polsku przy formularzu; lista z filtrem miesiąca; usuwanie z potwierdzeniem (`window.confirm`). Po mutacji odświeżenie listy i podsumowania (invalidate queries).
- Wszystkie teksty w `src/i18n/pl.ts` (N06). Proste, czytelne style w jednym pliku CSS (bez bibliotek UI w E1).
- Testy vitest: `formatMoney` (np. `"-1234.5"` → zawiera `1234,50` i `zł`), mapowanie `ai_status` na komunikat.

## Kryteria akceptacji
- [ ] `make check-web` przechodzi
- [ ] przy działającym `make dev-api` + `make dev-web` da się przejść UC-09, UC-10, UC-11, UC-12

## Poza zakresem
shadcn/ui, wykresy, import CSV, edycja transakcji, SSE.
