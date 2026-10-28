# UC-07 — Ocena wpływu zakupu na portfel

## Aktor

[Użytkownik](../glossary.md)

## Aktorzy pomocniczy

Dostawca modelu językowego (zewnętrzna usługa, z której korzysta **agent AI**)

## Cel

Sprawdzenie przed podjęciem decyzji, jak zakup wybranego aktywa zmieni udział **klas aktywów** w **portfelu**.

## Powiązane wymagania

[F23](../requirements.md#43-portfel), [F32, F33, F37](../requirements.md#44-agent-ai), [N03, N08](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- Użytkownik widzi udział klas aktywów przed zakupem i po nim oraz ocenę agenta AI z uzasadnieniem i zastrzeżeniem, że nie jest to porada inwestycyjna.
- Portfel się nie zmienił, a system nie wykonał żadnej operacji finansowej (założenie Z5).

## Scenariusz podstawowy

1. Użytkownik wskazuje aktywo (klasę aktywów, nazwę lub ticker) i planowaną kwotę lub ilość zakupu.
2. System ustala ostatnio znaną cenę aktywa i przelicza ją na walutę bazową.
3. System oblicza udział klas aktywów w portfelu przed zakupem i po zakupie.
4. System przekazuje agentowi AI wynik obliczeń, skład portfela i profil inwestycyjny, bez danych osobowych (N03).
5. Agent AI ocenia, jak zakup wpłynie na dywersyfikację portfela i jego zgodność z profilem inwestycyjnym, i uzasadnia ocenę.
6. System pokazuje porównanie udziałów przed i po zakupie, ocenę agenta AI, uzasadnienie i zastrzeżenie.

## Scenariusze alternatywne

- **1a. Użytkownik przechodzi z listy okazji (UC-06):** Aktywo jest już wskazane, więc użytkownik podaje tylko kwotę lub ilość.
- **2a. System nie zna ceny aktywa:** System prosi użytkownika o podanie ceny ręcznie i wraca do kroku 2.
- **3a. Portfel jest pusty:** System pokazuje, że po zakupie aktywo stanowiłoby 100% portfela, a agent AI uwzględnia to w uzasadnieniu.
- **4a. Profil inwestycyjny nie jest uzupełniony:** Agent AI ocenia tylko zmianę udziału klas aktywów. Uzasadnienie wspomina o braku profilu, a system proponuje jego uzupełnienie (UC-05).
- **5a. Usługa agenta AI jest niedostępna:** System pokazuje samo porównanie udziałów z kroku 3 i informuje, że ocena agenta jest chwilowo niedostępna (N08).
- **5b. Ocena agenta nie ma uzasadnienia:** System nie pokazuje oceny, tylko porównanie udziałów (F32).

## Uwagi i otwarte kwestie

- Czy ocena powinna uwzględniać budżet, np. czy planowana kwota mieści się w nadwyżce z ostatniego miesiąca?
