# UC-04 — Zarządzanie pozycjami portfela

## Aktor

[Użytkownik](../glossary.md)

## Cel

Odwzorowanie w systemie aktualnego składu **portfela**: dodanie, edycja lub usunięcie **pozycji**.

## Powiązane wymagania

[F20, F21, F22, F23, F25](../requirements.md#43-portfel)

## Warunek wstępny

- Użytkownik jest zalogowany.
- Użytkownik zna skład swojego portfela (założenie Z2).

## Warunek końcowy

- Portfel zawiera pozycje zgodne z danymi podanymi przez użytkownika.
- **Wartość portfela** i udział każdej **klasy aktywów** są przeliczone w walucie bazowej.

## Scenariusz podstawowy

1. Użytkownik wybiera dodanie pozycji.
2. System prosi o klasę aktywów, nazwę lub ticker, ilość, cenę zakupu i datę zakupu.
3. Użytkownik podaje dane i zatwierdza.
4. System sprawdza poprawność danych.
5. System zapisuje pozycję.
6. System pokazuje zaktualizowaną wartość portfela i udział klas aktywów.

## Scenariusze alternatywne

- **1a. Edycja pozycji:** Użytkownik wybiera pozycję z portfela. System pokazuje jej dane. Scenariusz trwa dalej od kroku 3.
- **1b. Usunięcie pozycji:** Użytkownik wybiera pozycję i jej usunięcie. System prosi o potwierdzenie, a po potwierdzeniu usuwa pozycję. Scenariusz trwa dalej od kroku 6.
- **4a. Niepoprawne dane (np. ilość ≤ 0, ujemna cena, data zakupu w przyszłości):** System wskazuje błędne pola i wraca do kroku 3.
- **4b. System nie rozpoznaje tickera aktywa notowanego:** System informuje, że nie będzie mógł aktualizować ceny tej pozycji (F25), i pyta, czy zapisać ją z ceną zakupu jako ostatnio znaną ceną.
- **4c. Cena zakupu jest w innej walucie niż bazowa:** System przelicza ją po kursie dziennym (założenie Z4).
- **6a. Brak aktualnej ceny dla pozycji:** System liczy wartość pozycji według ceny zakupu i oznacza ją jako nieaktualną.

## Uwagi i otwarte kwestie

- Jak opisać pozycje bez tickera i ilości (gotówka, lokata, nieruchomość)? Czy wystarczy nazwa i kwota?
- Czy dokupienie aktywa, które już jest w portfelu, tworzy nową pozycję, czy zmienia istniejącą?
