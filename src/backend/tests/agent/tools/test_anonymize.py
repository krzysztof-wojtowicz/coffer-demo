import pytest

from coffer.agent.anonymize import scrub


@pytest.mark.parametrize(
    "text",
    [
        "PL61109010140000071219812874",
        "61109010140000071219812874",
        "PL61 1090 1014 0000 0712 1981 2874",
        "61 1090 1014 0000 0712 1981 2874",
    ],
)
def test_iban(text):
    assert scrub(f"Przelew na {text} dziękuję") == "Przelew na [RACHUNEK] dziękuję"


def test_email():
    assert scrub("pisz do jan.kowalski+x@example.co.uk teraz") == "pisz do [EMAIL] teraz"


@pytest.mark.parametrize("card", ["4111111111111111", "4111 1111 1111 1111"])
def test_card_number(card):
    assert scrub(f"karta {card} koniec") == "karta [NUMER] koniec"


def test_amount_untouched():
    for s in ["Zapłacono 1 234,56 zł", "Kwota 6009,63", "12,50 PLN"]:
        assert scrub(s) == s


def test_plain_text_and_short_numbers_untouched():
    s = "Biedronka 2025 nr 12345"
    assert scrub(s) == s


def test_multiple():
    out = scrub("a@b.pl PL61109010140000071219812874 4111111111111111")
    assert out == "[EMAIL] [RACHUNEK] [NUMER]"
