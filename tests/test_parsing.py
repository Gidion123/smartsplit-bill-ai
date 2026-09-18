import pytest

from modules.parsing import extract_json, parse_amount, parse_quantity


@pytest.mark.parametrize(
    "text, expected",
    [
        ("25.000", 25000),
        ("25,000", 25000),
        ("Rp 1.250.500", 1250500),
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("12.50", 12.5),
        ("-5.000", -5000),
        ("(2.500)", -2500),
        (18000, 18000),
        ("abc", None),
        (None, None),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text, expected", [("2", 2), ("2x", 2), ("x3", 3), ("", 1), (None, 1), (0, 1)])
def test_parse_quantity(text, expected):
    assert parse_quantity(text) == expected


def test_extract_json_from_markdown_block():
    raw = 'Berikut hasilnya:\n```json\n{"total": 10000}\n```'
    assert extract_json(raw) == {"total": 10000}


def test_extract_json_without_json_raises():
    with pytest.raises(ValueError):
        extract_json("maaf, gambar tidak terbaca")
