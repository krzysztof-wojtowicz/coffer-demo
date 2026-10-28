# UC-05 — Uzupełnienie profilu inwestycyjnego

## Aktor

[Użytkownik](../glossary.md)

## Cel

Zadeklarowanie horyzontu inwestycji, tolerancji ryzyka i preferowanych **klas aktywów**, aby **sugestie** agenta AI były dopasowane do użytkownika.

## Powiązane wymagania

[F30](../requirements.md#44-agent-ai)

## Warunek wstępny

- Użytkownik jest zalogowany.

## Warunek końcowy

- **Profil inwestycyjny** jest zapisany.
- Kolejne sugestie agenta AI (UC-06, UC-07) uwzględniają aktualny profil.

## Scenariusz podstawowy

1. Użytkownik wybiera profil inwestycyjny.
2. System pokazuje formularz profilu, a jeśli profil już istnieje, wypełnia go obecnymi wartościami.
3. Użytkownik podaje horyzont inwestycji, tolerancję ryzyka (niska / średnia / wysoka) i preferowane klasy aktywów, a następnie zatwierdza.
4. System sprawdza, czy profil jest kompletny.
5. System zapisuje profil i potwierdza zapisanie.

## Scenariusze alternatywne

- **3a. Użytkownik anuluje:** System nie zmienia profilu.
- **4a. Profil jest niekompletny (brak horyzontu, tolerancji ryzyka lub żadnej preferowanej klasy aktywów):** System wskazuje brakujące pola i wraca do kroku 3.

## Uwagi i otwarte kwestie

- Trzeba ustalić format horyzontu inwestycji: liczba lat czy kategorie (krótki / średni / długi).
- Zmiana profilu nie zmienia sugestii, które użytkownik już otrzymał.
