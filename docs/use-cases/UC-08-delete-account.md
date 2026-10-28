# UC-08 — Usunięcie konta

## Aktor

[Użytkownik](../glossary.md)

## Cel

Trwałe usunięcie konta wraz ze wszystkimi danymi użytkownika.

## Powiązane wymagania

[F09](../requirements.md#41-konto-i-dane), [N02, N09](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- Konto i wszystkie dane użytkownika (transakcje, portfel, profil inwestycyjny, limity, cele) są trwale usunięte (N09).
- Nie da się zalogować na usunięte konto.

## Scenariusz podstawowy

1. Użytkownik wybiera usunięcie konta.
2. System informuje, że operacja jest nieodwracalna i usunie wszystkie dane.
3. System prosi o potwierdzenie hasłem.
4. Użytkownik podaje hasło i potwierdza usunięcie.
5. System sprawdza hasło.
6. System trwale usuwa konto i wszystkie dane użytkownika.
7. System wylogowuje użytkownika i potwierdza usunięcie konta.

## Scenariusze alternatywne

- **2a. Użytkownik chce najpierw wyeksportować dane:** System eksportuje dane do pliku CSV (F09) i wraca do kroku 2.
- **4a. Użytkownik rezygnuje:** System nic nie usuwa.
- **5a. Błędne hasło:** System informuje o błędzie i wraca do kroku 3.

## Uwagi i otwarte kwestie

- Eksport danych (F09) ma priorytet C, więc 2a działa tylko wtedy, gdy eksport zostanie zrealizowany.
- Czy po usunięciu konta ten sam adres e-mail może posłużyć do założenia nowego konta?
- Trzeba ustalić, co z danymi w kopiach zapasowych.
