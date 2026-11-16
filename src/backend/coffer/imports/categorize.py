import re
from collections.abc import Mapping

from coffer.transactions.service import normalize_description

RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Przelewy własne", ("PRZELEW WŁASNY", "PRZELEW WLASNY", "NA KONTO OSZCZĘDNOŚCIOWE")),
    ("Inwestycje", ("DOM MAKLERSKI", "XTB", "BOSSA", "OBLIGACJE SKARBOWE")),
    ("Wynagrodzenie", ("WYNAGRODZENIE", "PENSJA", "WYPŁATA")),
    (
        "Jedzenie",
        (
            "BIEDRONKA",
            "LIDL",
            "ŻABKA",
            "AUCHAN",
            "KAUFLAND",
            "CARREFOUR",
            "STOKROTKA",
            "DINO",
            "NETTO",
            "LECLERC",
            "PIEKARNIA",
            "RESTAURACJA",
            "PIZZA",
            "MCDONALD",
            "KFC",
            "STARBUCKS",
            "GLOVO",
            "PYSZNE",
            "WOLT",
            "CUKIERNIA",
            "KAWIARNIA",
        ),
    ),
    (
        "Transport",
        (
            "MPK",
            "ORLEN",
            "PKP",
            "UBER",
            "BOLT",
            "SHELL",
            "BP ",
            "CIRCLE K",
            "MOL ",
            "INTERCITY",
            "FLIXBUS",
            "PARKING",
            "TAXI",
            "JAKDOJADE",
            "KOLEJE",
            "AUTOSTRADA",
        ),
    ),
    ("Mieszkanie", ("CZYNSZ", "IKEA", "LEROY", "CASTORAMA", "OBI ", "WSPÓLNOTA", "KAUCJA")),
    (
        "Rachunki",
        (
            "PRĄD",
            "TAURON",
            "GAZ",
            "INTERNET",
            "ORANGE",
            "PLAY ",
            "T-MOBILE",
            "PLUS ",
            "UPC",
            "VECTRA",
            "PGE",
            "ENEA",
            "WODOCIĄGI",
            "ENERGA",
            "PGNIG",
        ),
    ),
    ("Zdrowie", ("APTEKA", "DOZ", "LUX MED", "MEDICOVER", "ZNANYLEKARZ", "PRZYCHODNIA", "DENTYST")),
    (
        "Rozrywka",
        (
            "NETFLIX",
            "SPOTIFY",
            "KINO",
            "HBO",
            "DISNEY",
            "CINEMA CITY",
            "MULTIKINO",
            "STEAM",
            "TEATR",
            "BILETY",
            "YOUTUBE",
        ),
    ),
    (
        "Zakupy",
        (
            "ALLEGRO",
            "ZALANDO",
            "AMAZON",
            "RTV EURO",
            "MEDIA MARKT",
            "DECATHLON",
            "EMPIK",
            "RESERVED",
            "HEBE",
            "ROSSMANN",
            "SINSAY",
            "H&M",
            "PEPCO",
            "OLX",
            "ALIEXPRESS",
        ),
    ),
]


def _compile(keyword: str) -> re.Pattern[str]:
    """Short keywords (DINO, NETTO, DOZ, "PLUS ") must not match inside longer words."""
    word = keyword.strip()
    pattern = re.escape(word)
    if len(word) <= 5:
        pattern = rf"(?<![^\W\d_]){pattern}(?![^\W\d_])"
    return re.compile(pattern)


_COMPILED: list[tuple[str, list[re.Pattern[str]]]] = [
    (category, [_compile(k) for k in keywords]) for category, keywords in RULES
]


def categorize(description: str, hints: Mapping[str, str] | None = None) -> str | None:
    """Exact hint (learned from the user's past choices) first, then keyword rules, else None."""
    if hints:
        hit = hints.get(normalize_description(description))
        if hit is not None:
            return hit
    upper = description.upper()
    for category, patterns in _COMPILED:
        if any(p.search(upper) for p in patterns):
            return category
    return None
