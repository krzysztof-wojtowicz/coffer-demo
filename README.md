# Coffer

[![CI](https://github.com/krzysztof-wojtowicz/coffer-demo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/krzysztof-wojtowicz/coffer-demo/actions/workflows/ci.yml)

Coffer to aplikacja do finansów osobistych: zbiera Twoje transakcje i inwestycje w jednym miejscu, liczy, ile zostaje Ci co miesiąc, i z pomocą asystenta AI podpowiada, co z tą nadwyżką zrobić.

**[Otwórz aplikację](https://cofferai.vercel.app)**

<!-- TODO: zrzuty ekranu -->

## Co potrafi Coffer

**Transakcje i import z banku**
- Dodajesz transakcje ręcznie (data, kwota, opis, kategoria) albo importujesz plik CSV z wyciągu.
- Przed importem widzisz podgląd: które wiersze są nowe, które to duplikaty już zapisanych transakcji, a które mają błędy. Sam decydujesz, co zaimportować.
- Transakcje z importu dostają kategorię automatycznie; te, których nie udało się przypisać, są oznaczone „do sprawdzenia”.

**Podsumowanie miesiąca**
- Dla wybranego miesiąca: przychody, wydatki, saldo i nadwyżka.
- Wydatki według kategorii z udziałem procentowym.

**Asystent AI: co zrobić z nadwyżką**
- Jednym kliknięciem prosisz asystenta o propozycję wykorzystania nadwyżki z danego miesiąca. Dostajesz krótką sugestię z uzasadnieniem i listą ryzyk.
- Przed wysłaniem widzisz dokładnie, jakie dane trafiają do modelu.
- Historia sugestii zostaje zapisana; jeśli w miesiącu nie ma nadwyżki, asystent mówi to wprost, bez angażowania modelu.

**Profil inwestycyjny**
- Trzy pytania: horyzont inwestycyjny, tolerancja ryzyka i preferowane klasy aktywów.
- Na tej podstawie Coffer pokazuje Twój profil (ostrożny, umiarkowany, dynamiczny) z orientacyjną alokacją, a asystent i doradca dopasowują do niego propozycje.

**Portfel**
- Pozycje inwestycyjne: akcje, ETF, obligacje, surowce, kryptowaluty, nieruchomości, gotówka i lokaty. Dodajesz, edytujesz i usuwasz je w dowolnej walucie.
- Pozycje z symbolem giełdowym (np. `AAPL`, `CDR.WA`, `BTC-USD`) są wyceniane po bieżących notowaniach, a kwoty w walutach obcych przeliczane na PLN po aktualnym kursie. Aktywa bez notowań (np. mieszkanie) wyceniasz ręcznie.
- Wartość portfela, koszt zakupu, zysk lub strata oraz alokacja według klas aktywów.
- **Doradca AI**: na podstawie struktury portfela i profilu proponuje „Top 3 dla Ciebie teraz” (instrumenty z poziomem ryzyka i uzasadnieniem) oraz porady z linkami do źródeł.

**Konto**
- Rejestracja e-mailem i hasłem, logowanie, wylogowanie. Każdy widzi wyłącznie własne dane.
- Strona *Konto*: zmiana hasła, wylogowanie ze wszystkich urządzeń, trwałe usunięcie konta razem ze wszystkimi danymi.

## Jak zacząć

1. **Załóż konto** na [stronie aplikacji](https://cofferai.vercel.app): wystarczy e-mail i hasło (min. 12 znaków, nie może być popularnym hasłem ani Twoim e-mailem).
2. **Dodaj transakcje.** Wpisz je ręcznie w zakładce *Transakcje* albo zaimportuj plik CSV w zakładce *Import* ([obsługiwany format](docs/csv-format.md)).
3. **Sprawdź podsumowanie** miesiąca na stronie głównej.
4. **Uzupełnij profil inwestycyjny** w zakładce *Profil*. Bez niego sugestie są mniej dopasowane.
5. **Dodaj portfel** w zakładce *Portfel*: pozycje, ilości, ceny zakupu.
6. **Poproś o rekomendacje**: w *Podsumowaniu* o pomysł na nadwyżkę, w *Portfelu* o propozycje doradcy AI.

## Prywatność i bezpieczeństwo

- **Do modelu AI trafiają tylko agregaty.** Asystent nadwyżki dostaje sumy miesiąca (przychody, wydatki, nadwyżka, wydatki per kategoria) i profil inwestycyjny. Doradca portfela dostaje udziały procentowe klas aktywów, symbole instrumentów i profil, bez kwot. Nigdy nie wysyłamy e-maila, opisów transakcji ani identyfikatorów.
- **Liczy aplikacja, nie model.** Wszystkie sumy i wyceny wylicza kod Coffera; model tylko je opisuje i proponuje pomysły. Gdy model jest niedostępny, reszta aplikacji działa normalnie.
- **Model w chmurze.** Wersja publiczna korzysta z zewnętrznego dostawcy modelu (Google Gemini), więc powyższe agregaty są przetwarzane przez niego zgodnie z jego regulaminem.
- **Hasła** są przechowywane wyłącznie jako skrót Argon2.
- **Sesja** jest trzymana w ciasteczku `HttpOnly` (niedostępnym dla skryptów strony); żądania zmieniające dane z obcych domen są odrzucane.
- **Dane w UE:** baza danych (Neon) i serwer aplikacji (Render) działają we Frankfurcie.

## Zastrzeżenie

Sugestie asystenta i rekomendacje doradcy mają charakter informacyjny i edukacyjny. **Nie są poradą inwestycyjną**; inwestowanie wiąże się z ryzykiem utraty kapitału, a decyzję podejmujesz samodzielnie. Notowania i kursy walut pochodzą z Yahoo Finance i mogą być opóźnione lub chwilowo niedostępne.

## Ograniczenia

- **Pierwsze wejście bywa wolne.** Serwer działa na darmowym planie i usypia po ok. 15 minutach bez ruchu; pierwsze żądanie po przerwie może trwać ok. 50 s.
- **Limit asystenta:** 50 zapytań o sugestię nadwyżki na użytkownika na dobę.
- **Import CSV** obsługuje na razie jeden format pliku (opisany w [docs/csv-format.md](docs/csv-format.md)), a nie wyciągi konkretnych banków.
- **Kursy walut i notowania** pochodzą tylko z Yahoo Finance. Gdy są niedostępne, pozycje wyceniane są z wyceny ręcznej lub ceny zakupu, a pozycji, których nie da się przeliczyć na PLN, nie wliczamy do sumy.
- Transakcji nie można edytować (można je usunąć i dodać ponownie).

## FAQ

**Czy Coffer łączy się z moim bankiem?**
Nie. Transakcje dodajesz ręcznie albo importujesz z pliku CSV. Coffer nie prosi o dane logowania do banku.

**Czy model AI widzi moje transakcje?**
Nie. Widzi tylko sumy miesiąca i wydatki per kategoria (asystent) albo procentową strukturę portfela i symbole (doradca). Na stronie asystenta możesz podejrzeć dokładnie, co zostanie wysłane.

**Czy zaimportowanie tego samego pliku dwa razy zdubluje transakcje?**
Nie. Podgląd importu oznacza transakcje, które już są w Coffer (ta sama data, kwota i opis), jako duplikaty i domyślnie ich nie importuje.

**Dlaczego asystent mówi, że jest niedostępny?**
Model AI chwilowo nie odpowiada albo wyczerpałeś dzienny limit zapytań. Podsumowanie, transakcje i portfel działają dalej; spróbuj ponownie później.

**Dlaczego wartość pozycji pokazuje „cena zakupu” zamiast „notowanie”?**
Nie udało się pobrać bieżącego notowania (brak symbolu, nieznany symbol lub chwilowa niedostępność Yahoo Finance). Wtedy pozycja jest wyceniana ręcznie albo po cenie zakupu.

**Dlaczego aplikacja długo się ładuje?**
Darmowy serwer usypia przy braku ruchu. Pierwsze wejście po przerwie trwa do ok. minuty, kolejne działają już szybko.

## Dla deweloperów

Coffer to monorepo: backend w Pythonie (FastAPI, PostgreSQL), frontend w React + TypeScript, asystent AI z wymiennym dostawcą modelu (Ollama lokalnie, Gemini, OpenAI lub Claude). Wersja publiczna działa na Vercel (frontend), Render (API) i Neon (baza).

- [Uruchomienie, konfiguracja i hosting](docs/hosting.md): instalacja lokalna, zmienne środowiskowe, dostawcy LLM, testy, struktura kodu
- [Architektura systemu](docs/architecture.md)
- [Wdrożenie produkcyjne: Neon, Render, Vercel, CI](docs/deploy/)
- [Serwer MCP danych rynkowych](docs/mcp-market.md)
- [Kontekst dla agentów AI (CLAUDE.md)](CLAUDE.md)

### Dokumentacja

- [Wizja](docs/vision.md)
- [Wymagania](docs/requirements.md)
- [Słownik](docs/glossary.md)
- [Przypadki użycia](docs/use-cases/README.md)
- [Plan techniczny](docs/plan.md)
- [Architektura systemu (diagramy)](docs/architecture.md)
- [Uruchomienie, konfiguracja i hosting](docs/hosting.md)
- [Wdrożenie: baza, backend, frontend, CI](docs/deploy/)
- [Serwer MCP danych rynkowych](docs/mcp-market.md)
- [Format CSV](docs/csv-format.md)
- [Praca z agentami](docs/agents.md)
- [Karty zadań](docs/tasks/README.md)

## O projekcie

Coffer powstaje na Politechnice Warszawskiej w ramach przedmiotów _Inżynieria Oprogramowania 1_ (specyfikacja) i _Tworzenie Agentów AI w środowisku .NET_ (integracja z agentem).

## Autorzy:

© Bartłomiej Sokołowski, Konstanty Sobczyński, Krzysztof Wójtowicz, Krzysztof Wojczakowski @ Politechnika Warszawska

### Grupy zajęciowe:

- **IO1** _Grupa 31_ - Bartłomiej Sokołowski, Konstanty Sobczyński, Krzysztof Wójtowicz
- **Agenci AI** _Grupa 4_ - Bartłomiej Sokołowski, Konstanty Sobczyński, Krzysztof Wójtowicz, Krzysztof Wojczakowski
