# Wymagania

Dokument opisuje, **co** system Coffer ma robić i w jakich granicach. Nie opisuje, jak to zbudować.
Znaczenie pogrubionych pojęć jest ustalone w [słowniku](glossary.md).

## 1. Priorytety

| Priorytet | Znaczenie |
|---|---|
| **M** (must) | Konieczne w pierwszej wersji. Bez tego system nie rozwiązuje problemu z wizji. |
| **S** (should) | Ważne, realizujemy zaraz po M. System bez tego działa, ale słabiej. |
| **C** (could) | Dodajemy, jeśli zostanie czas. |
| **W** (won't) | Świadomie poza zakresem tej wersji. |

## 2. Niejednoznaczności znalezione w wizji

| # | Fragment wizji | Problem | Przyjęta decyzja |
|---|---|---|---|
| N1 | „wieloźródłowe zarządzanie finansami” | Nie wiadomo, skąd dane trafiają do systemu, skoro integracja z API banku jest poza zakresem. | Dane wprowadza **użytkownik** ręcznie lub przez import pliku CSV z wyciągu bankowego. (chyba że API banku jest dostępne). |
| N2 | „budżet rodziny / małej firmy / przedsiębiorstwa” | Firma ma inne potrzeby (VAT, księgowość, wielu użytkowników z uprawnieniami). | Pierwsza wersja obsługuje **budżet osobisty** jednej osoby. Firmy — W. |
| N3 | „gdzie i jak zainwestować nadwyżkę”, „co najlepiej pasuje do mojego portfela” | Brzmi jak doradztwo inwestycyjne, które jest usługą regulowaną. | System prezentuje **sugestie** informacyjne z uzasadnieniem i zastrzeżeniem, nie rekomendacje. |
| N4 | „prognozy” | Nie wiadomo, czego dotyczą i na jaki horyzont. | Prognoza dotyczy salda **budżetu i aktywów** na koniec bieżącego i kolejnego miesiąca. |
| N5 | „aktywa / nieruchomości” | Nie wiadomo, jakie klasy aktywów system rozumie. | Obsługiwane klasy: gotówka, lokaty, akcje, ETF, obligacje, kryptowaluty, nieruchomości. |
| N6 | „okazje” | Brak kryterium, co jest okazją. | **Okazja** to aktywo spełniające kryteria zapisane w **profilu inwestycyjnym** użytkownika (patrz słownik). |

## 3. Ukryte założenia

- **Z1.** Użytkownik ma dostęp do historii swoich transakcji (np. wyciąg z banku w CSV) i chce ją wprowadzić do systemu.
- **Z2.** Użytkownik zna skład swojego **portfela** (ile i jakich aktywów posiada) i wpisze go samodzielnie.
- **Z3.** Użytkownik ma dostęp do Internetu podczas korzystania z funkcji agenta AI.
- **Z4.** Jedna waluta bazowa na użytkownika (domyślnie PLN); inne waluty są przeliczane po kursie dziennym.
- **Z5.** System nie wykonuje żadnych operacji finansowych — tylko analizuje i informuje.
- **Z6.** Użytkownik akceptuje, że dane finansowe są przechowywane przez system.

## 4. Wymagania funkcjonalne

### 4.1 Konto i dane

| ID | Wymaganie | Źródło w wizji | Priorytet |
|---|---|---|---|
| F01 | Użytkownik może założyć konto, podając adres e-mail i hasło. | Użytkownicy | M |
| F02 | Użytkownik widzi wyłącznie własne dane finansowe. | Użytkownicy | M |
| F03 | Użytkownik może ręcznie dodać **transakcję** (data, kwota, opis, **kategoria**). | Problem | M |
| F04 | Użytkownik może zaimportować transakcje z pliku CSV. | Problem (wieloźródłowość) | M |
| F05 | System przy imporcie pomija transakcje, które już istnieją (ta sama data, kwota i opis). | Problem | S |
| F06 | Użytkownik może edytować i usunąć transakcję. | Problem | M |
| F07 | System automatycznie przypisuje kategorię do zaimportowanej transakcji. | Scenariusz: analiza miesięczna | S |
| F08 | Użytkownik może zmienić kategorię przypisaną przez system. | Scenariusz: analiza miesięczna | M |
| F09 | Użytkownik może wyeksportować wszystkie swoje dane do pliku CSV. | Problem | C |

### 4.2 Analiza budżetu

| ID | Wymaganie | Źródło w wizji | Priorytet |
|---|---|---|---|
| F10 | System pokazuje sumę wydatków w wybranym miesiącu w podziale na kategorie. | Scenariusz: analiza miesięczna | M |
| F11 | System pokazuje sumę przychodów i wydatków oraz **nadwyżkę** dla wybranego miesiąca. | Scenariusz: analiza miesięczna | M |
| F12 | System porównuje wydatki w każdej kategorii z poprzednim miesiącem i pokazuje zmianę w PLN i w %. | Scenariusz: analiza miesięczna | S |
| F13 | Użytkownik może ustawić miesięczny **limit wydatków** dla kategorii. | Scenariusz: oszczędzanie | S |
| F14 | System oznacza kategorię, w której wydatki przekroczyły ustawiony limit. | Scenariusz: oszczędzanie | S |
| F15 | System wskazuje 3 kategorie, w których wydatki najbardziej wzrosły względem średniej z 3 poprzednich miesięcy. | Scenariusz: oszczędzanie | S |
| F16 | Użytkownik może ustawić **cel oszczędnościowy** (kwota i termin). | Scenariusz: oszczędzanie | C |
| F17 | System pokazuje, jaką kwotę trzeba odkładać miesięcznie, aby osiągnąć cel oszczędnościowy w terminie. | Scenariusz: oszczędzanie | C |
| F18 | System prognozuje saldo na koniec bieżącego miesiąca na podstawie dotychczasowych transakcji. | Problem (prognozy) | C |

### 4.3 Portfel

| ID | Wymaganie | Źródło w wizji | Priorytet |
|---|---|---|---|
| F20 | Użytkownik może dodać **aktywo** do portfela (klasa, nazwa/ticker, ilość, cena zakupu, data zakupu). | Scenariusz: zakup aktywów | M |
| F21 | Użytkownik może edytować i usunąć aktywo z portfela. | Scenariusz: zakup aktywów | M |
| F22 | System pokazuje bieżącą **wartość portfela** w walucie bazowej. | Scenariusz: zakup aktywów („ile i co już mam”) | M |
| F23 | System pokazuje udział procentowy każdej klasy aktywów w wartości portfela. | Scenariusz: zakup aktywów | M |
| F24 | System pokazuje zysk/stratę każdego aktywa względem ceny zakupu. | Scenariusz: zakup aktywów | S |
| F25 | System aktualizuje ceny aktywów notowanych co najmniej raz dziennie. | Scenariusz: zakup aktywów | S |

### 4.4 Agent AI

| ID | Wymaganie | Źródło w wizji | Priorytet |
|---|---|---|---|
| F30 | Użytkownik może uzupełnić **profil inwestycyjny** (horyzont, tolerancja ryzyka, preferowane klasy aktywów). | Rola agenta | M |
| F31 | Agent na żądanie użytkownika generuje **sugestię** dotyczącą wykorzystania nadwyżki z wybranego miesiąca. | Scenariusz: analiza miesięczna | M |
| F32 | Każda sugestia zawiera uzasadnienie odwołujące się do danych użytkownika (portfel, budżet, profil). | Rola agenta | M |
| F33 | Każda sugestia wyświetla zastrzeżenie, że nie jest poradą inwestycyjną. | Niejednoznaczność N3 | M |
| F34 | Agent na żądanie wyszukuje w Internecie informacje o wskazanej spółce i zwraca podsumowanie. | Scenariusz: zakup aktywów | S |
| F35 | Podsumowanie z F34 zawiera listę źródeł (adresy URL), z których pochodzą informacje. | Scenariusz: zakup aktywów | S |
| F36 | Agent wskazuje **okazje** zgodne z profilem inwestycyjnym użytkownika. | Rola agenta | C |
| F37 | Agent ocenia, jak zakup wskazanego aktywa zmieni udział klas aktywów w portfelu. | Scenariusz: zakup aktywów („co pasuje do portfela”) | S |
| F38 | Użytkownik może zadawać agentowi pytania w formie czatu dotyczące jego danych. | Rola agenta („chat-pomocnik”) | C |

### 4.5 Poza zakresem (W)

| ID | Wymaganie | Uzasadnienie |
|---|---|---|
| W1 | Wykonywanie płatności i przelewów. | Wizja: bramka płatnicza poza zakresem. |
| W2 | Automatyczne pobieranie transakcji z banku przez API. | Wizja: integracja z API banku poza zakresem. |
| W3 | Samodzielne kupowanie aktywów przez agenta. | Wizja: autonomiczne zakupy poza zakresem. |
| W4 | Wspólny budżet wielu użytkowników (rodzina, firma). | Niejednoznaczność N2. |

## 5. Wymagania niefunkcjonalne

| ID | Kategoria | Wymaganie (warunek sprawdzalny) | Priorytet |
|---|---|---|---|
| N01 | Bezpieczeństwo | Hasła są przechowywane wyłącznie w postaci skrótu z solą; żadne miejsce w systemie nie zawiera hasła jawnym tekstem. | M |
| N02 | Bezpieczeństwo | Użytkownik niezalogowany nie ma dostępu do żadnych danych finansowych (każde żądanie bez sesji kończy się odmową). | M |
| N03 | Bezpieczeństwo | Dane użytkownika nie są przekazywane do zewnętrznego modelu AI bez identyfikatorów osobowych (imię, e-mail, numer konta). | M |
| N04 | Poprawność | Sumy kwot w podsumowaniach są zgodne co do grosza z sumą transakcji źródłowych. | M |
| N05 | Poprawność | Automatyczna kategoryzacja (F07) przypisuje właściwą kategorię co najmniej 80% transakcji na zbiorze testowym 200 transakcji. | C |
| N06 | Użyteczność | Interfejs i komunikaty systemu są w języku polskim. | M |
| N07 | Wiarygodność | Każda informacja rynkowa podana przez agenta ma datę pobrania. | S |
| N08 | Dostępność | Funkcje z grup 4.1–4.3 działają, gdy usługa agenta AI jest niedostępna. | S |
| N09 | Prywatność | Użytkownik może trwale usunąć konto wraz ze wszystkimi danymi. | S |

