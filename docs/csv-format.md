# Testowy format CSV („Coffer Test Bank”)

Wymyślony format do rozwoju i testów importu (UC-02) przed obsługą prawdziwych banków. Dane w repo są wyłącznie fikcyjne. Przykład: [`data/fixtures/csv/testbank-2026-10.csv`](../data/fixtures/csv/testbank-2026-10.csv).

## Format pliku

| Cecha | Wartość |
|---|---|
| Kodowanie | UTF-8 (bez BOM) |
| Separator | `;` |
| Wiersze nagłówka | 1 |
| Data | `DD.MM.RRRR` |
| Kwota | przecinek dziesiętny, spacja jako separator tysięcy (`-1 234,56`); ujemna = wydatek |
| Waluta | kod ISO 4217 (`PLN`, `EUR`, …) |

| Kolumna | Użycie przy imporcie |
|---|---|
| `Data operacji` | data transakcji |
| `Data księgowania` | pomijana |
| `Opis` | opis transakcji (może zawierać nazwiska i numery kont, więc przed wysłaniem do AI wymaga anonimizacji, N03) |
| `Kwota` | kwota w walucie oryginalnej |
| `Waluta` | waluta oryginalna; obecnie obsługiwane jest tylko `PLN`, wiersz w innej walucie dostaje błąd „Waluta … nie jest jeszcze obsługiwana” (przeliczanie po kursie dziennym jest planowane) |
| `Saldo po operacji` | pomijana |

## Deduplikacja i kategoryzacja

- **Duplikat (F05):** wiersz o tej samej dacie, kwocie i opisie (po normalizacji spacji i bez rozróżniania wielkości liter) co transakcja już zapisana. Porównanie dotyczy tylko zakresu dat z pliku i jest wielozbiorowe: dwie identyczne transakcje w pliku przy jednej w bazie dają jedną nową i jednego duplikata.
- **Kategoria (F07):** najpierw dokładne trafienie w opis, który użytkownik już kiedyś skategoryzował (podpowiedź z jego własnych poprawek, F08), potem reguły słów kluczowych; wiersz bez trafienia dostaje kategorię domyślną i znacznik „do sprawdzenia”. Skuteczność reguł (N05, min. 80%) sprawdza test na zbiorze 200 wymyślonych transakcji.

## Konfiguracja banku

Importer nie ma klasy per bank, tylko konfigurację. Prawdziwe banki dodamy później jako kolejne wpisy:

```toml
[banks.testbank]
name = "Coffer Test Bank"
encoding = "utf-8"
delimiter = ";"
skip_rows = 1
date_format = "%d.%m.%Y"
decimal_separator = ","
thousands_separator = " "
columns = { date = "Data operacji", description = "Opis", amount = "Kwota", currency = "Waluta" }
```

## Przypadki zawarte w przykładowym pliku
- dwa identyczne bilety MPK tego samego dnia (deduplikacja jako multizbiór, F05),
- transakcja w EUR (przeliczenie walut),
- przelew z nazwiskiem i numerem rachunku w opisie (anonimizacja),
- przelew własny i zasilenie rachunku maklerskiego (kategorie spoza budżetu),
- przychody: wynagrodzenie i zwrot od znajomej osoby.
