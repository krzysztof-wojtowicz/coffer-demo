# UC-03 — Edycja i usunięcie transakcji, zmiana kategorii

## Aktor

[Użytkownik](../glossary.md)

## Cel

Poprawienie lub usunięcie błędnej **transakcji** albo zmiana jej **kategorii**, aby analizy opierały się na prawdziwych danych.

## Powiązane wymagania

[F05, F06, F08](../requirements.md#41-konto-i-dane), [N04](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.
- Użytkownik ma co najmniej jedną transakcję.

## Warunek końcowy

- Zmiana jest zapisana: transakcja ma nowe dane albo nie ma jej w systemie.
- Podsumowania budżetu uwzględniają zmianę i zgadzają się co do grosza z transakcjami źródłowymi (N04).

## Scenariusz podstawowy

1. Użytkownik wybiera transakcję z listy.
2. System pokazuje dane transakcji: datę, kwotę, opis i kategorię.
3. Użytkownik zmienia wybrane pola, w tym kategorię, i zatwierdza zmiany.
4. System sprawdza poprawność danych.
5. System zapisuje zmiany i potwierdza ich zapisanie.

## Scenariusze alternatywne

- **3a. Użytkownik wybiera usunięcie transakcji:** System prosi o potwierdzenie. Po potwierdzeniu usuwa transakcję i informuje o tym. Scenariusz się kończy.
- **3b. Użytkownik nie potwierdza usunięcia:** System nic nie usuwa i wraca do kroku 2.
- **3c. Użytkownik anuluje edycję:** System nie zapisuje zmian.
- **4a. Niepoprawne dane (np. kwota nie jest liczbą, kwota równa 0, brak daty):** System wskazuje błędne pola i wraca do kroku 3.
- **4b. Po zmianie transakcja ma tę samą datę, kwotę i opis co inna transakcja:** System ostrzega o możliwym duplikacie (F05) i pyta, czy mimo to zapisać zmiany.

## Uwagi i otwarte kwestie

- Czy ręczna zmiana kategorii ma wpływać na późniejszą automatyczną kategoryzację (F07)?
- Czy usunięcie transakcji można cofnąć?
