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

1. Użytkownik uruchamia akcję agenta `investment_ideas` (*Nowe możliwości inwestycyjne*) i opcjonalnie podaje kwotę, miesiąc lub klasę aktywów.
2. System przekazuje agentowi AI profil inwestycyjny i skład portfela, bez danych osobowych (N03).
3. Agent AI wyszukuje aktywa z preferowanych klas aktywów, zgodne z horyzontem i tolerancją ryzyka.
4. System odrzuca aktywa, które już są w portfelu.
5. Agent AI przygotowuje dla każdej okazji uzasadnienie odwołujące się do profilu i portfela.
6. System pokazuje listę okazji z uzasadnieniem, datą pobrania informacji rynkowych (N07) i zastrzeżeniem.
7. Użytkownik przegląda listę i sam podejmuje decyzję.

## Scenariusze alternatywne

- **1a. Profil inwestycyjny nie jest uzupełniony:** System informuje, że do wskazania okazji potrzebny jest profil, i proponuje jego uzupełnienie (UC-05). Po uzupełnieniu profilu scenariusz wraca do kroku 1.
- **3a. Usługa agenta AI jest niedostępna (lub limit dzienny, timeout):** System pokazuje wynik regułowy (te same kryteria, bez AI, oznaczony „bez AI”). Pozostałe funkcje działają normalnie (N08).
- **4a. Nie znaleziono żadnej okazji:** System informuje, że żadne aktywo nie spełnia kryteriów profilu. Scenariusz się kończy.
- **5a. Okazja nie ma uzasadnienia:** System jej nie pokazuje (F32).
- **7a. Użytkownik chce sprawdzić, jak zakup okazji zmieni portfel:** Użytkownik przechodzi do oceny wpływu zakupu (UC-07) dla wybranego aktywa.

## Uwagi i otwarte kwestie

- Rozstrzygnięte: kandydatów daje stałe uniwersum instrumentów (`get_instrument_universe`) z poziomem ryzyka 1–5, notowania i wiadomości pochodzą z Yahoo Finance; pokazujemy 3 pomysły. Limit czasu akcji to `COFFER_AGENT_TIMEOUT_S`. Wyniki nie są cache'owane (każde uruchomienie liczy od nowa; historia zapisuje wcześniejsze).
- Przy braku profilu akcja nie jest blokowana: używa profilu domyślnego i to zaznacza (odstępstwo od 1a).
