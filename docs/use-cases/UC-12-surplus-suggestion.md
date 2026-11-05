# UC-12 — Sugestia wykorzystania nadwyżki

## Aktor

[Użytkownik](../glossary.md)

## Aktorzy pomocniczy

Dostawca modelu językowego (zewnętrzna usługa, z której korzysta **agent AI**)

## Cel

Dowiedzieć się, jak mogę wykorzystać **nadwyżkę** z wybranego miesiąca, razem z uzasadnieniem opartym na moich danych.

## Powiązane wymagania

[F31](../requirements.md#44-agent-ai), [F32, F33](../requirements.md#44-agent-ai), [N03, N08](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- Użytkownik widzi nadwyżkę z wybranego miesiąca oraz **sugestię** z uzasadnieniem i zastrzeżeniem, że nie jest to porada inwestycyjna.
- Do modelu językowego trafiły wyłącznie zanonimizowane agregaty (N03).
- System nie wykonał żadnej operacji finansowej.

## Scenariusz podstawowy

1. Użytkownik wybiera miesiąc i prosi o sugestię wykorzystania nadwyżki.
2. System liczy nadwyżkę deterministycznie, bez udziału modelu (jak w UC-11).
3. System sprawdza, że nadwyżka jest większa od 0.
4. System wysyła do modelu językowego wyłącznie zanonimizowane agregaty: sumy, kategorie, udziały i **profil inwestycyjny**. Nie wysyła adresu e-mail ani opisów transakcji (N03).
5. Agent AI tworzy sugestię z uzasadnieniem.
6. System sprawdza, czy odpowiedź zawiera uzasadnienie odwołujące się do danych użytkownika (F32).
7. System pokazuje nadwyżkę, sugestię, uzasadnienie i zastrzeżenie (F33).

## Scenariusze alternatywne

- **3a. Nadwyżka wynosi 0 lub jest ujemna:** System informuje, że w tym miesiącu nie ma nadwyżki, pokazuje wyliczenia i nie wywołuje modelu. Scenariusz się kończy.
- **4a. Brak profilu inwestycyjnego:** System wysyła same agregaty budżetu, agent AI tworzy sugestię ogólną, a system zachęca do uzupełnienia profilu (UC-05).
- **5a. Model niedostępny lub przekroczony limit czasu:** System pokazuje samo wyliczenie nadwyżki i komunikat „Asystent AI jest chwilowo niedostępny” (N08). Scenariusz się kończy.
- **6a. Odpowiedź bez uzasadnienia:** System odrzuca odpowiedź i postępuje jak w 5a.

## Uwagi i otwarte kwestie

- Brak wymagania na limit czasu odpowiedzi modelu — trzeba go ustalić (dotyczy też 5a).
- Czy „zanonimizowane agregaty” mają obejmować nazwy kategorii zdefiniowanych przez użytkownika, które mogą zawierać dane osobowe?
- Czy sugestia ma uwzględniać portfel użytkownika (F32 wymienia portfel, budżet i profil)? Tu przyjęto budżet i profil.
- Czy system ma ponawiać wywołanie modelu przy błędzie?
- Jak traktować miesiąc bieżący, który się jeszcze nie zakończył (nadwyżka niepełna)?
