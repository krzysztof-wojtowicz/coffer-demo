# EX-YY: Nazwa zadania

**Fala:** N · **Zależności:** EX-ZZ · **Role:** implementer + tester · **UC / wymagania:** UC-XX, FXX

## Cel
Jedno–dwa zdania: co działa po zakończeniu.

## Przeczytaj
Tylko pliki potrzebne do zadania (agent nie czyta niczego poza nimi i swoimi plikami).
- `CLAUDE.md` (ładuje się automatycznie)
- `docs/use-cases/UC-XX-....md`
- `src/backend/tests/conftest.py` (fikstury)

## Pliki
- **implementer:** `src/backend/coffer/<moduł>/{api,service,schemas}.py`
- **tester:** `src/backend/tests/<moduł>/`

## Kontrakt
Endpointy (metoda, ścieżka, wejście, wyjście, kody błędów z komunikatami), sygnatury funkcji `service.py`, reguły biznesowe.

## Kryteria akceptacji
- [ ] `make lint` przechodzi
- [ ] testy testera przechodzą
- [ ] ...

## Poza zakresem
Co świadomie zostaje na później.
