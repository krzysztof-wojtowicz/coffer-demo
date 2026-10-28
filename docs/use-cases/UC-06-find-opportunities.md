# UC-06 — Wskazanie okazji

## Aktor

[Użytkownik](../glossary.md)

## Aktorzy pomocniczy

Dostawca modelu językowego (zewnętrzna usługa, z której korzysta **agent AI**)

## Cel

Poznanie **okazji**, czyli aktywów, których nie ma w **portfelu**, a które spełniają kryteria **profilu inwestycyjnego** użytkownika.

## Powiązane wymagania

[F30, F32, F33, F36](../requirements.md#44-agent-ai), [N03, N07, N08](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.
- Użytkownik ma uzupełniony profil inwestycyjny (UC-05).
- Użytkownik ma dostęp do Internetu (założenie Z3).

## Warunek końcowy

- Użytkownik otrzymał listę okazji z uzasadnieniem i zastrzeżeniem, że nie jest to porada inwestycyjna.
- System nie wykonał żadnej operacji finansowej (założenie Z5).

## Scenariusz podstawowy

1. Użytkownik prosi agenta AI o wskazanie okazji.
2. System przekazuje agentowi AI profil inwestycyjny i skład portfela, bez danych osobowych (N03).
3. Agent AI wyszukuje aktywa z preferowanych klas aktywów, zgodne z horyzontem i tolerancją ryzyka.
4. System odrzuca aktywa, które już są w portfelu.
5. Agent AI przygotowuje dla każdej okazji uzasadnienie odwołujące się do profilu i portfela.
6. System pokazuje listę okazji z uzasadnieniem, datą pobrania informacji rynkowych (N07) i zastrzeżeniem.
7. Użytkownik przegląda listę i sam podejmuje decyzję.

## Scenariusze alternatywne

- **1a. Profil inwestycyjny nie jest uzupełniony:** System informuje, że do wskazania okazji potrzebny jest profil, i proponuje jego uzupełnienie (UC-05). Po uzupełnieniu profilu scenariusz wraca do kroku 1.
- **3a. Usługa agenta AI jest niedostępna:** System informuje, że wskazanie okazji jest chwilowo niedostępne. Pozostałe funkcje działają normalnie (N08).
- **4a. Nie znaleziono żadnej okazji:** System informuje, że żadne aktywo nie spełnia kryteriów profilu. Scenariusz się kończy.
- **5a. Okazja nie ma uzasadnienia:** System jej nie pokazuje (F32).
- **7a. Użytkownik chce sprawdzić, jak zakup okazji zmieni portfel:** Użytkownik przechodzi do oceny wpływu zakupu (UC-07) dla wybranego aktywa.

## Uwagi i otwarte kwestie

- Z jakiego źródła agent AI bierze listę aktywów do przeszukania (wyszukiwarka, serwis notowań)?
- Ile okazji pokazujemy jednocześnie?
