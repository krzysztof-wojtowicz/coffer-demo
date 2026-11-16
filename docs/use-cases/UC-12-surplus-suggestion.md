# UC-12 — Sugestia wykorzystania nadwyżki (akcja `investment_ideas`)

## Aktor

[Użytkownik](../glossary.md)

## Aktorzy pomocniczy

Dostawca modelu językowego (zewnętrzna usługa, z której korzysta **agent AI**)

## Cel

Dowiedzieć się, jak mogę wykorzystać **nadwyżkę** z wybranego miesiąca, razem z uzasadnieniem opartym na moich danych.

## Powiązane wymagania

[F31](../requirements.md#44-agent-ai), [F32, F33](../requirements.md#44-agent-ai), [N03, N08](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- Użytkownik widzi kwotę do zainwestowania (domyślnie **nadwyżkę** z wybranego miesiąca) oraz **sugestię**: listę pomysłów na instrumenty z uzasadnieniem i zastrzeżeniem, że nie jest to porada inwestycyjna.
- Do modelu językowego trafiły wyłącznie agregaty (N03).
- System nie wykonał żadnej operacji finansowej.

## Scenariusz podstawowy

Realizuje go akcja agenta `investment_ideas` (*Nowe możliwości inwestycyjne*, zakładka *Doradca AI*); parametry opcjonalne: miesiąc (domyślnie poprzedni), kwota, klasa aktywów.

1. Użytkownik wybiera akcję, opcjonalnie podaje miesiąc, kwotę lub klasę aktywów, i uruchamia ją.
2. Jeśli kwota nie została podana, system przyjmuje za nią nadwyżkę wybranego miesiąca, policzoną deterministycznie bez udziału modelu (jak w UC-11).
3. System pobiera profil inwestycyjny i skład portfela, liczy lukę alokacji i dobiera kandydatów z uniwersum instrumentów (bez tych, które użytkownik już ma).
4. System wysyła do modelu językowego wyłącznie agregaty i kandydatów: kwotę, udziały klas, poziom ryzyka, profil. Nie wysyła adresu e-mail ani opisów transakcji (N03). Model może dociągnąć notowania i wiadomości narzędziami akcji.
5. Agent AI uzasadnia wybór pomysłów (top 3).
6. System sprawdza, czy odpowiedź zawiera uzasadnienie odwołujące się do danych użytkownika (F32) i czy liczby pochodzą z wyników narzędzi.
7. System pokazuje kwotę wraz ze źródłem (nadwyżka z miesiąca albo kwota podana), pomysły z uzasadnieniem, źródła i zastrzeżenie (F33). Przebieg ma **ślad** (kroki i narzędzia) dostępny z historii.

## Scenariusze alternatywne

- **2a. Nadwyżka wynosi 0 lub jest ujemna, a użytkownik nie podał kwoty:** Akcja kończy się statusem `no_data` z komunikatem „Brak nadwyżki w wybranym miesiącu. Podaj kwotę ręcznie.”; model nie jest wywoływany. Podanie kwoty ręcznie pozwala uruchomić akcję dla dowolnego miesiąca.
- **3a. Brak profilu inwestycyjnego:** System przyjmuje profil domyślny (umiarkowane ryzyko, średni horyzont), zaznacza to w raporcie i zachęca do uzupełnienia profilu (UC-05).
- **3b. Brak kandydatów:** Akcja kończy się statusem `no_data` („Brak instrumentów spełniających kryteria. Zmień klasę aktywów.”).
- **5a. Model niedostępny, limit dzienny wyczerpany, przekroczony limit czasu albo odpowiedź odrzucona przez walidator:** System pokazuje **wynik regułowy** (fallback bez AI): ten sam wybór pomysłów z uzasadnieniem z reguł, oznaczony jako „bez AI” (N08). Przebieg trafia do historii ze statusem `unavailable`, `limited`, `timeout` albo `invalid`.
- **\*a. Zbyt wiele uruchomień akcji:** Przy przekroczeniu ochrony przed nadużyciem (20/min, 200/dobę, 2 równolegle) system odpowiada komunikatem „Zbyt wiele uruchomień akcji…” (HTTP 429).

## Uwagi i otwarte kwestie

- Stan implementacji: UC-12 realizuje akcja `investment_ideas` z katalogu sześciu akcji panelu *Doradca AI* (`/assistant`); nadwyżka jest domyślną kwotą, a nie warunkiem. Do F31 należą też akcje `savings_analysis` i `budget_plan`. Osobne endpointy nadwyżki i doradcy portfela zostały usunięte na rzecz jednego mechanizmu akcji.
- Rozstrzygnięte: limit czasu to `COFFER_AGENT_TIMEOUT_S` (domyślnie 60 s, dotyczy całej akcji); portfel uwzględniamy (luka alokacji); przy błędzie walidacji następuje jedna poprawka (`COFFER_AGENT_MAX_ATTEMPTS`=2), potem wynik regułowy.
- Czy „zanonimizowane agregaty” mają obejmować nazwy kategorii zdefiniowanych przez użytkownika? Kategorie są dziś globalne (słownik systemowy), więc problem nie występuje.
- Miesiąc bieżący (niepełny): domyślnym miesiącem jest poprzedni; użytkownik może wskazać bieżący, a nadwyżka jest wtedy niepełna.
