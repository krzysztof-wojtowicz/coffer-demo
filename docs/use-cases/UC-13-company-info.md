# UC-13 — Wyszukanie informacji o spółce

## Aktor

[Użytkownik](../glossary.md)

## Aktorzy pomocniczy

- Dostawca modelu językowego (zewnętrzna usługa, z której korzysta **agent AI**)
- Wyszukiwarka internetowa (zewnętrzna usługa, z której korzysta agent AI)

## Cel

Szybko poznać aktualne informacje o spółce, którą rozważam kupić, wraz ze źródłami, które mogę sprawdzić.

## Powiązane wymagania

[F34, F35](../requirements.md#44-agent-ai), [N07, N08](../requirements.md#5-wymagania-niefunkcjonalne)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- Użytkownik widzi podsumowanie informacji o spółce, listę źródeł (adresy URL) i datę pobrania informacji (F35, N07).
- Agent AI nie otrzymał żadnych danych użytkownika, a system nie zmienił portfela ani budżetu.

## Scenariusz podstawowy

1. Użytkownik podaje nazwę lub ticker spółki i prosi o informacje.
2. System przekazuje agentowi AI wyłącznie nazwę lub ticker spółki. Agent nie ma dostępu do danych użytkownika.
3. Agent AI wyszukuje informacje o spółce w Internecie.
4. Agent AI tworzy podsumowanie na podstawie znalezionych źródeł.
5. System pokazuje podsumowanie, listę źródeł (URL) i datę pobrania informacji.

## Scenariusze alternatywne

- **3a. Wyszukiwarka nie zwraca wyników:** System informuje, że nie znaleziono informacji o spółce, i proponuje sprawdzenie nazwy lub tickera. Scenariusz wraca do kroku 1.
- **3b. Przekroczony limit czasu wyszukiwania lub tworzenia podsumowania:** System informuje o przekroczeniu czasu i proponuje ponowienie. Scenariusz się kończy.
- **4a. Model językowy niedostępny:** System informuje, że asystent AI jest chwilowo niedostępny (N08). Scenariusz się kończy.
- **4b. Podsumowanie nie ma żadnego źródła:** System nie pokazuje podsumowania i postępuje jak w 3a, bo F35 wymaga listy źródeł.

## Uwagi i otwarte kwestie

- Nazwa spółki jest niejednoznaczna (kilka spółek o podobnej nazwie lub ticker na różnych giełdach) — czy system ma prosić o doprecyzowanie?
- Brak wymagania na limit czasu (3b) — trzeba go ustalić.
- Czy podsumowanie wymaga zastrzeżenia, że nie jest poradą? F33 dotyczy sugestii, a tu agent tylko streszcza informacje.
- Czy dopuszczamy zapamiętanie wyniku (cache), skoro data pobrania ma być widoczna?
- Czy 4b nie powinno być zapisane jako wymaganie (podsumowanie bez źródeł jest odrzucane)?
