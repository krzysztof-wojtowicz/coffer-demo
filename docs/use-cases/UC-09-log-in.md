# UC-09 — Logowanie i wylogowanie

## Aktor

[Użytkownik](../glossary.md)

## Cel

Uzyskanie dostępu do własnych danych finansowych po zalogowaniu i bezpieczne zakończenie pracy przez wylogowanie.

## Powiązane wymagania

[F01, F02](../requirements.md#41-konto-i-dane), [N02](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik ma konto w systemie (UC-01).

## Warunek końcowy

- Po zalogowaniu: użytkownik ma aktywną sesję i widzi wyłącznie własne dane (F02).
- Po wylogowaniu: sesja jest unieważniona, a każde żądanie bez ważnej sesji kończy się odmową (N02).

## Scenariusz podstawowy

1. Użytkownik podaje adres e-mail i hasło.
2. System sprawdza dane logowania.
3. System tworzy sesję ważną 14 dni i pokazuje dane użytkownika.
4. Użytkownik wybiera wylogowanie.
5. System natychmiast unieważnia sesję i potwierdza wylogowanie.

## Scenariusze alternatywne

- **2a. Błędny adres e-mail lub hasło:** System pokazuje jeden wspólny komunikat „Nieprawidłowy e-mail lub hasło”, niezależnie od tego, czy konto istnieje. Scenariusz wraca do kroku 1.
- **2b. Brak adresu e-mail lub hasła:** System wskazuje puste pola i wraca do kroku 1.
- **3a. Sesja wygasa po 14 dniach:** Kolejne żądanie kończy się odmową, a system przekierowuje użytkownika do logowania (krok 1).
- **4a. Użytkownik używa unieważnionej sesji (np. cofnięciem w przeglądarce):** System odmawia dostępu do danych i przekierowuje do logowania (N02).

## Uwagi i otwarte kwestie

- Czy po serii nieudanych prób logowania system ma blokować konto lub opóźniać kolejne próby? Wymagania tego nie określają.
- Czy użytkownik może mieć kilka sesji naraz (kilka urządzeń) i czy wylogowanie unieważnia wszystkie, czy tylko bieżącą?
- Czy 14 dni liczy się od zalogowania, czy od ostatniej aktywności? Wartość 14 dni nie występuje w `requirements.md` — warto ją tam dopisać.
- Brak w wymaganiach funkcji odzyskiwania hasła.
