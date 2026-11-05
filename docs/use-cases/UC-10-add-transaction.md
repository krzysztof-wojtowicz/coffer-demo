# UC-10 — Ręczne dodanie transakcji

## Aktor

[Użytkownik](../glossary.md)

## Cel

Dodanie **transakcji**, której nie ma w pliku z banku, aby **budżet** odzwierciedlał wszystkie moje przepływy pieniędzy.

## Powiązane wymagania

[F03](../requirements.md#41-konto-i-dane), [N04, N06](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- Nowa transakcja jest zapisana z datą, kwotą w PLN, opisem i dokładnie jedną **kategorią**.
- Podsumowania budżetu uwzględniają transakcję i zgadzają się co do grosza z transakcjami źródłowymi (N04).

## Scenariusz podstawowy

1. Użytkownik wybiera dodanie transakcji.
2. Użytkownik podaje datę, kwotę, opis i kategorię. Kwota ujemna oznacza **wydatek**, dodatnia — **przychód**.
3. System sprawdza poprawność danych.
4. System zapisuje transakcję w walucie PLN i potwierdza jej zapisanie.

## Scenariusze alternatywne

- **2a. Użytkownik nie wybiera kategorii:** System przypisuje kategorię domyślną „Inne”.
- **3a. Niepoprawne dane (kwota nie jest liczbą, kwota równa 0, kwota z więcej niż 2 miejscami po przecinku, brak daty):** System wskazuje błędne pola w języku polskim (N06) i wraca do kroku 2.
- **3b. Transakcja ma tę samą datę, kwotę i opis co istniejąca:** System ostrzega o możliwym duplikacie i pyta, czy mimo to zapisać. Gdy użytkownik odmówi, wraca do kroku 2.
- **1a. Użytkownik anuluje dodawanie:** System nic nie zapisuje.

## Uwagi i otwarte kwestie

- Ostrzeżenie o duplikacie (3b) wynika z F05 i dotyczy dziś importu; trzeba potwierdzić, że obejmuje też ręczne dodawanie.
- Czy data w przyszłości jest dozwolona?
- Czy kategorię „Inne” trzeba dopisać do słownika jako kategorię systemową? Obecnie `glossary.md` jej nie wymienia.
- Czy użytkownik może dodać własną kategorię, czy wybiera tylko z listy predefiniowanej?
