# UC-02 — Import transakcji z pliku CSV

## Aktor

[Użytkownik](../glossary.md)

## Cel

Wprowadzenie do systemu historii **transakcji** z wyciągu bankowego bez ręcznego przepisywania.

## Powiązane wymagania

[F04, F05, F07, F08](../requirements.md#41-konto-i-dane), [N04](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.
- Użytkownik ma plik CSV z wyciągiem bankowym.

## Warunek końcowy

- Nowe transakcje z pliku są zapisane, każda z dokładnie jedną **kategorią**.
- Transakcje, które już były w systemie, nie zostały zapisane ponownie.

## Scenariusz podstawowy

1. Użytkownik wybiera import transakcji.
2. Użytkownik wskazuje plik CSV.
3. System odczytuje plik i rozpoznaje transakcje (data, kwota, opis).
4. System pomija transakcje, które już istnieją (ta sama data, kwota i opis).
5. System przypisuje kategorię każdej nowej transakcji.
6. System pokazuje podgląd: liczbę nowych i pominiętych transakcji oraz przypisane kategorie.
7. Użytkownik zatwierdza import.
8. System zapisuje nowe transakcje i potwierdza liczbę zaimportowanych pozycji.

## Scenariusze alternatywne

- **3a. Plik nie jest poprawnym plikiem CSV lub brakuje wymaganych kolumn:** System informuje o błędzie i wskazuje brakujące kolumny. Import się kończy, nic nie zostaje zapisane.
- **3b. Część wierszy jest niepoprawna (np. kwota nie jest liczbą):** System pomija te wiersze i podaje ich numery. Scenariusz trwa dalej od kroku 4.
- **4a. Wszystkie transakcje z pliku już istnieją:** System informuje, że nie ma nowych transakcji. Import się kończy.
- **5a. System nie potrafi dopasować kategorii:** System przypisuje kategorię domyślną i oznacza transakcję do weryfikacji w podglądzie.
- **6a. Użytkownik zmienia kategorię w podglądzie:** System zapamiętuje kategorię wybraną przez użytkownika (F08, por. UC-03) i wraca do kroku 6.
- **7a. Użytkownik anuluje import:** System nic nie zapisuje.

## Uwagi i otwarte kwestie

- Trzeba ustalić nazwę kategorii domyślnej (np. „Inne”) i dopisać ją do [słownika](../glossary.md).
- Trzeba ustalić, jakie formaty CSV (banki) obsługujemy w pierwszej wersji.
- Transakcje w innej walucie niż **waluta bazowa** są przeliczane po kursie dziennym (założenie Z4).
