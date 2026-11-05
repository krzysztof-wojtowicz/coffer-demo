from dataclasses import dataclass, field


@dataclass(frozen=True)
class BankConfig:
    id: str
    name: str
    encoding: str = "utf-8"
    delimiter: str = ";"
    skip_rows: int = 1
    date_format: str = "%d.%m.%Y"
    decimal_separator: str = ","
    thousands_separator: str = " "
    columns: dict[str, str] = field(default_factory=dict)


BANKS: dict[str, BankConfig] = {
    "testbank": BankConfig(
        id="testbank",
        name="Coffer Test Bank",
        columns={
            "date": "Data operacji",
            "description": "Opis",
            "amount": "Kwota",
            "currency": "Waluta",
        },
    ),
}
