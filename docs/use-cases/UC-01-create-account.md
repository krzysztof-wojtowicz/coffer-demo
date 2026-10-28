# UC-01 — Założenie konta

## Aktor

[Użytkownik](../glossary.md) (osoba, która nie ma jeszcze konta)

## Cel

Założenie konta, w którym użytkownik będzie przechowywać i analizować własne dane finansowe.

## Powiązane wymagania

[F01, F02](../requirements.md#41-konto-i-dane), [N01, N06](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik nie ma konta w systemie.

## Warunek końcowy

- Konto istnieje, a hasło jest zapisane wyłącznie jako skrót z solą (N01).
- Konto ma ustawioną **walutę bazową** PLN (założenie Z4).
- Użytkownik jest zalogowany i widzi puste konto, bez danych innych użytkowników (F02).

## Scenariusz podstawowy

1. Użytkownik wybiera założenie konta.
2. System prosi o adres e-mail i hasło oraz pokazuje informację, że dane finansowe będą przechowywane przez system.
3. Użytkownik podaje adres e-mail i hasło oraz akceptuje informację o przechowywaniu danych (założenie Z6).
4. System sprawdza format adresu e-mail i zasady dotyczące hasła.
5. System sprawdza, czy adres e-mail nie jest już zarejestrowany.
6. System tworzy konto z walutą bazową PLN i zapisuje skrót hasła.
7. System potwierdza założenie konta i loguje użytkownika.

## Scenariusze alternatywne

- **3a. Użytkownik nie akceptuje informacji o przechowywaniu danych:** System nie zakłada konta i informuje, że bez tej zgody nie może działać.
- **4a. Niepoprawny format adresu e-mail:** System informuje o błędzie i wraca do kroku 3.
- **4b. Hasło nie spełnia zasad:** System pokazuje zasady, których hasło nie spełnia, i wraca do kroku 3.
- **5a. Adres e-mail jest już zarejestrowany:** System informuje, że nie może założyć konta na ten adres, i proponuje logowanie. Scenariusz się kończy.

## Uwagi i otwarte kwestie

- Trzeba ustalić zasady dotyczące hasła (minimalna długość, rodzaje znaków) i ewentualnie dopisać je jako wymaganie niefunkcjonalne.
- Czy wymagamy potwierdzenia adresu e-mail linkiem aktywacyjnym?
- Komunikat z 5a pozwala sprawdzić, czy dany adres ma konto. Trzeba zdecydować, czy to akceptujemy.
- Logowanie nie ma osobnego przypadku użycia. Pozostałe przypadki zakładają, że użytkownik jest zalogowany (N02).
