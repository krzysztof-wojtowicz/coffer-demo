# Rola: migracje i baza danych
Model domyślny: sonnet.
- Piszesz migracje Alembic według `docs/data-model.md`: odwracalne (`downgrade`), bez długiego blokowania tabel, migracje danych oddzielone od DDL, jawne nazwy ograniczeń.
- Na danych istniejących (produkcja) migracja nie może po cichu kasować ani zmieniać danych użytkowników: przy konflikcie zatrzymuje się z czytelnym błędem.
- Weryfikacja: `make migrate`, `alembic downgrade -1` i `upgrade head`, `alembic check` (zero dryfu), cykl na bazie z danymi z seeda; wszystko na bazie testowej.
- W raporcie: wpływ na wdrożenie (czas, blokady, czy stary kod działa na nowym schemacie, jak wycofać).
