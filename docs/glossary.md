# Słownik

Jedno pojęcie — jedno znaczenie. Jeśli słowo z tej listy pada w wizji lub wymaganiach, znaczy dokładnie to, co poniżej.

| Pojęcie | Znaczenie w projekcie |
|---|---|
| **Użytkownik** | Jedna osoba fizyczna posiadająca konto w systemie i zarządzająca własnymi finansami. |
| **Budżet** | Zestawienie przychodów i wydatków użytkownika w danym miesiącu kalendarzowym. |
| **Transakcja** | Pojedynczy przepływ pieniędzy na rachunku użytkownika: data, kwota (dodatnia — przychód, ujemna — wydatek), opis, kategoria. |
| **Przychód** | Transakcja zwiększająca środki użytkownika (np. wynagrodzenie). |
| **Wydatek** | Transakcja zmniejszająca środki użytkownika. |
| **Kategoria** | Etykieta grupująca transakcje według celu (np. jedzenie, transport, mieszkanie). Każda transakcja ma dokładnie jedną. |
| **Nadwyżka** | Przychody minus wydatki w danym miesiącu z kategorii budżetowych (bez Inwestycji i Przelewów własnych), gdy wynik jest dodatni. Kafelki miesiąca (Przychody, Wydatki, Balans) liczą wszystkie transakcje miesiąca i nie są nadwyżką; akcja *Nowe możliwości inwestycyjne* używa nadwyżki jako domyślnej kwoty. Suma balansów miesięcy równa się sumie transakcji, a „Środki na kontach” to ta suma plus saldo początkowe. |
| **Limit wydatków** | Maksymalna kwota, jaką użytkownik zamierza wydać w danej kategorii w ciągu miesiąca. Ustala ją użytkownik. |
| **Limit kategorii** | Zapisany w aplikacji limit wydatków dla jednej kategorii budżetowej (tabela `budget_limits`, jeden stały limit miesięczny). Zużycie limitu liczy `analytics`; akcja *Plan budżetu* może zaproponować limity do zastosowania. |
| **Cel oszczędnościowy** | Kwota, którą użytkownik chce zgromadzić do określonej daty. |
| **Aktywo** | Składnik majątku użytkownika należący do jednej z klas: gotówka, lokata, akcje, ETF, obligacje, kryptowaluty, nieruchomość. |
| **Klasa aktywów** | Jedna z siedmiu grup wymienionych w definicji *aktywa*. |
| **Pozycja** | Konkretne aktywo w portfelu wraz z ilością, ceną i datą zakupu (np. 10 akcji spółki X kupionych 01.03 po 50 zł). |
| **Portfel** | Zbiór wszystkich pozycji użytkownika. |
| **Wartość portfela** | Suma wartości wszystkich pozycji według ostatnio znanej ceny, w walucie bazowej. |
| **Waluta bazowa** | Waluta, w której system pokazuje wszystkie sumy (domyślnie PLN). |
| **Profil inwestycyjny** | Deklaracja użytkownika: horyzont inwestycji, tolerancja ryzyka (niska / średnia / wysoka) i preferowane klasy aktywów. |
| **Sugestia** | Informacja wygenerowana przez agenta AI z uzasadnieniem opartym na danych użytkownika i zastrzeżeniem, że nie jest poradą. Decyzję zawsze podejmuje użytkownik. |
| **Okazja** | Aktywo, które spełnia kryteria profilu inwestycyjnego użytkownika i którego jeszcze nie ma w portfelu. |
| **Analiza miesięczna** | Zestaw podsumowań dla jednego miesiąca: wydatki wg kategorii, przychody, nadwyżka, zmiana względem poprzedniego miesiąca. |
| **Majątek (wartość netto)** | Środki na kontach plus wartość portfela. Środki na kontach to saldo początkowe (kwota i data podane przez użytkownika) plus suma transakcji od tej daty do dziś; bez salda liczone od zera; flaga `portfolio_complete` mówi, czy cały portfel ma aktualną wycenę. |
| **Prognoza** | Szacunek salda budżetu na koniec miesiąca wyliczony z dotychczasowych transakcji. |
| **Agent AI** | Część systemu korzystająca z modelu językowego, która na żądanie użytkownika uruchamia akcje: tworzy sugestie, wyszukuje informacje i analizuje dane. |
| **Akcja agenta** | Jedna funkcja AI z katalogu sześciu (`portfolio_review`, `investment_ideas`, `savings_analysis`, `purchase_impact`, `budget_plan`, `company_research`), uruchamiana jednym mechanizmem (`POST /api/agent/actions/{id}/run`). Ma parametry, listę dozwolonych narzędzi, wersjonowany prompt i wynik regułowy. |
| **Katalog narzędzi** | Rejestr 22 narzędzi (dane użytkownika, obliczenia, dane rynkowe), które aplikacja i model wołają w trakcie akcji; każda akcja ma własną listę dozwolonych narzędzi. |
| **Przebieg (ślad)** | Zapis jednego uruchomienia akcji (`agent_runs`): parametry, kroki, wywołane narzędzia, zużycie tokenów, czas i status. Użytkownik może go obejrzeć w historii. |
| **Krok śladu** | Pojedynczy element przebiegu: wywołanie narzędzia, wywołanie modelu, walidacja, fallback, limit lub błąd. |
| **Wynik regułowy (fallback)** | Raport akcji zbudowany bez modelu z policzonych faktów, pokazywany, gdy AI jest niedostępne, wyczerpano limit, upłynął czas albo odpowiedź modelu była niepoprawna. Oznaczony jako „bez AI” (`source: rules`). |
| **Job cen** | Odświeżanie notowań i kursów walut do tabeli `market_quotes`: komenda `make prices` albo opcjonalny wątek w API (`COFFER_PRICE_REFRESH_HOURS`, domyślnie wyłączony). |
