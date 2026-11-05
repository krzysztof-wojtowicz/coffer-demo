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
| `Waluta` | waluta oryginalna (obca → przeliczenie po kursie NBP, Etap 2) |
| `Saldo po operacji` | pomijana |

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
