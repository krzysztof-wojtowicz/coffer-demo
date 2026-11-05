# UC-11 — Analiza miesięczna budżetu

## Aktor

[Użytkownik](../glossary.md)

## Cel

Zobaczenie, na co wydałem pieniądze w wybranym miesiącu, ile zarobiłem i jaka jest moja **nadwyżka**.

## Powiązane wymagania

[F10, F11, F12, F13, F14, F15](../requirements.md#42-analiza-budżetu), [N04, N08](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- Użytkownik widzi **analizę miesięczną** dla wybranego miesiąca: wydatki wg kategorii, sumę przychodów i wydatków oraz nadwyżkę.
- Sumy zgadzają się co do grosza z transakcjami źródłowymi (N04).
- System nie zmienił żadnych danych.

## Scenariusz podstawowy

1. Użytkownik wybiera miesiąc.
2. System wybiera transakcje z tego miesiąca, pomijając kategorie „Przelewy własne” i „Inwestycje”.
3. System liczy sumę wydatków w podziale na kategorie (F10) oraz sumę przychodów, sumę wydatków i nadwyżkę (F11).
4. System porównuje wydatki w każdej kategorii z poprzednim miesiącem i podaje zmianę w PLN i w % (F12).
5. System sprawdza **limity wydatków** i oznacza kategorie, w których limit przekroczono (F14), oraz wskazuje 3 kategorie o największym wzroście względem średniej z 3 poprzednich miesięcy (F15).
6. System pokazuje analizę miesięczną.

## Scenariusze alternatywne

- **2a. Miesiąc nie ma transakcji:** System pokazuje zera w sumach i komunikat, że brak transakcji w tym miesiącu. Scenariusz się kończy.
- **3a. Wydatki przewyższają przychody:** Nadwyżka wynosi 0 (zgodnie ze słownikiem nadwyżka jest dodatnia), a system pokazuje deficyt.
- **4a. Brak danych z poprzedniego miesiąca:** System pomija porównanie dla tego miesiąca i informuje o braku danych.
- **5a. Użytkownik nie ustawił limitów:** System pomija oznaczenia przekroczeń i proponuje ustawienie limitu (F13).
- **5b. Mniej niż 3 poprzednie miesiące z danymi:** System liczy średnią z dostępnych miesięcy albo pomija wskazanie F15 i informuje o tym.
- **\*a. Usługa agenta AI jest niedostępna:** Analiza działa bez zmian, bo nie korzysta z agenta AI (N08).

## Uwagi i otwarte kwestie

- Kategorie „Przelewy własne” i „Inwestycje” nie są wymienione w `glossary.md` ani w `requirements.md`; trzeba je dopisać (jako kategorie systemowe wyłączone z analizy).
- Czy transfery i inwestycje w ogóle mają trafiać do analizy jako osobna informacja (np. ile przeznaczono na inwestycje)?
- Jak pokazywać nadwyżkę ujemną: jako 0 czy jako deficyt? Słownik definiuje nadwyżkę tylko dla wyniku dodatniego.
- Jak liczyć zmianę w %, gdy wydatki w poprzednim miesiącu wynosiły 0?
- F12–F15 mają priorytet S, a F10–F11 — M; można rozdzielić UC na część podstawową i dodatkową.
- Ustawianie limitów (F13) nie ma osobnego UC.
