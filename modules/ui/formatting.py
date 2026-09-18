"""Format tampilan angka uang."""

from __future__ import annotations

# kode -> (simbol, jumlah desimal, pemisah ribuan, pemisah desimal)
CURRENCIES = {
    "IDR": ("Rp", 0, ".", ","),
    "SGD": ("S$", 2, ",", "."),
    "MYR": ("RM", 2, ",", "."),
    "USD": ("$", 2, ",", "."),
}


def currency_decimals(currency: str) -> int:
    return CURRENCIES.get(currency, CURRENCIES["IDR"])[1]


def format_money(amount: float, currency: str = "IDR") -> str:
    """Contoh: format_money(125000) -> 'Rp125.000', format_money(-5000) -> '-Rp5.000'."""
    symbol, decimals, thousand, decimal = CURRENCIES.get(currency, CURRENCIES["IDR"])
    text = f"{abs(amount):,.{decimals}f}"  # format bawaan python: 125,000.00
    text = text.replace(",", "\0").replace(".", decimal).replace("\0", thousand)
    sign = "-" if round(amount, decimals) < 0 else ""
    return f"{sign}{symbol}{text}"


def format_qty(qty: float) -> str:
    return f"{qty:g}"
