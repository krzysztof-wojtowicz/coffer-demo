# E5-11: Aktualizacja dokumentacji po Etapie 5

**Fala:** E5/5 · **Zależności:** E5-01..E5-10 · **Role:** dokumentacja (bilbo) · **UC / wymagania:** wszystkie dotknięte w E5

## Cel
Dokumentacja opisuje stan po Etapie 5: jeden mechanizm akcji agenta zamiast nadwyżki i doradcy, katalog akcji i narzędzi, ślad, limity kategorii, porównania miesięcy, job cen. Żaden plik `.md` nie odsyła do usuniętych endpointów, plików ani zmiennych (`/api/agent/surplus`, `/api/agent/investment/advice`, `COFFER_ADVISOR_TIMEOUT_S`, `AdvisorPanel`).

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (całość) i sekcje „Kontrakt” kart E5-01..E5-09; raporty kart (od orkiestratora)
- Przed edycją każdego pliku: `grep -n "surplus\|nadwyżk\|advisor\|doradc\|investment/advice\|ADVISOR_TIMEOUT\|0007\|fx_rates\|market_quotes\|budget_limits" <plik>` i czytanie tylko trafionych fragmentów
- Kod tylko do sprawdzenia faktów (`grep`), bez zmian

## Pliki
- **bilbo:** `README.md`, `docs/architecture.md`, `docs/data-model.md`, `docs/requirements.md`, `docs/use-cases/{README,UC-06-find-opportunities,UC-07-assess-purchase-impact,UC-11-monthly-analysis,UC-12-surplus-suggestion,UC-13-company-info}.md`, `docs/agents.md`, `docs/glossary.md`, `docs/plan.md`, `docs/hosting.md`, `docs/deploy/{backend,release-checklist}.md`, `docs/mcp-market.md` (tylko jeśli opis współdzielenia narzędzi z doradcą jest nieaktualny)

## Kontrakt (zakres zmian)
- **README:** funkcje AI jako katalog 6 akcji; `make prices`, `COFFER_PRICE_REFRESH_HOURS`, `COFFER_AGENT_TIMEOUT_S`; zrzut struktury `agent/`.
- **architecture.md:** sekcja 5 („Pobierz rekomendacje”) → sekwencja „Uruchom akcję” (prepare → limit → pętla narzędzi → walidacja → fallback → zapis śladu i sugestii; SSE); diagram modułów z `agent/actions`, `runner`, `trace`, `pricing`; nowe moduły `analytics`; job cen w diagramie wdrożenia (wątek opcjonalny, CLI).
- **data-model.md:** stan rzeczywisty migracji 0007–0009 (kolumny `agent_runs`/`suggestions`, `llm_usage_daily`, `budget_limits`, `market_quotes`); poprawiony plan numeracji w §4 (0006 = saldo początkowe; co z planu zrealizowano, co zostaje: `fx_rates` po dacie, `code` kategorii, `user_settings`, purge); retencja nowych tabel.
- **requirements.md:** bez zmiany treści wymagań; tabela/uwaga śledzenia: F31 → `investment_ideas`/`budget_plan`, F34–F37 → akcje, F12–F15, F25 zrealizowane. Zmiany znaczenia wymagań tylko jako propozycje w raporcie.
- **use-cases:** UC-12 przepisany na akcję `investment_ideas` (nadwyżka jako domyślna kwota, `no_data` zamiast „brak nadwyżki”); UC-06, UC-07, UC-13: rozstrzygnięte „Uwagi i otwarte kwestie” (limit czasu = `COFFER_AGENT_TIMEOUT_S`, nadwyżka jako fakt w UC-07, zastrzeżenie w UC-13, brak cache wyników); UC-11: limity i porównania; `use-cases/README.md` – mapowanie UC → akcja.
- **glossary.md:** akcja agenta, katalog narzędzi, przebieg (ślad), krok śladu, wynik regułowy (fallback), limit kategorii, job cen.
- **agents.md:** podział ról i fal Etapu 5 jako przykład pracy równoległej (rozłączne pliki, polityka `make openapi` z E5-00 D12).
- **plan.md:** sekcja „Etap 5” (cel, karty, stan), aktualizacja Etapu 4 (co przeniesiono do E5, np. E4-03); bez przepisywania historii innych etapów.
- **hosting.md, deploy/*:** zmienne `COFFER_AGENT_TIMEOUT_S` (zamiast `ADVISOR`), `COFFER_PRICE_REFRESH_HOURS` (na Render free: 0, uzasadnienie z D8), komenda `make prices`.

## Kryteria akceptacji
- [ ] `grep -rn "investment/advice\|/api/agent/surplus\|ADVISOR_TIMEOUT\|AdvisorPanel" README.md docs/ --include=*.md` → tylko `docs/tasks/` (historia kart)
- [ ] wszystkie linki względne w zmienionych plikach istnieją (sprawdzone skryptem lub `grep` + `ls`)
- [ ] polski język, styl istniejących dokumentów; diagramy mermaid się parsują (składnia jak w istniejących)

## Poza zakresem
`docs/tasks/README.md` i karty (orkiestrator), `CLAUDE.md` (propozycje zmian w raporcie, np. lista modułów `analytics`), `vision.md`.
