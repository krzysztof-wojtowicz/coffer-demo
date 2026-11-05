RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Przelewy własne", ("PRZELEW WŁASNY",)),
    ("Inwestycje", ("DOM MAKLERSKI",)),
    ("Wynagrodzenie", ("WYNAGRODZENIE",)),
    ("Jedzenie", ("BIEDRONKA", "LIDL", "ŻABKA", "AUCHAN")),
    ("Transport", ("MPK", "ORLEN", "PKP", "UBER", "BOLT")),
    ("Mieszkanie", ("CZYNSZ",)),
    ("Rachunki", ("PRĄD", "TAURON", "GAZ", "INTERNET")),
    ("Zdrowie", ("APTEKA",)),
    ("Rozrywka", ("NETFLIX", "SPOTIFY", "KINO")),
    ("Zakupy", ("ALLEGRO", "ZALANDO")),
]


def categorize(description: str) -> str | None:
    upper = description.upper()
    for category, keywords in RULES:
        if any(k in upper for k in keywords):
            return category
    return None
