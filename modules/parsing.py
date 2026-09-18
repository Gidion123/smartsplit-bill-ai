"""
Fungsi bantu untuk mengubah teks mentah hasil model menjadi angka/JSON.

Model lokal (Donut, Qwen) mengeluarkan teks, bukan angka. Masalah paling
sering di nota Indonesia adalah format harga, misalnya:
    "25.000"      -> 25000   (titik = pemisah ribuan)
    "25,000"      -> 25000   (koma = pemisah ribuan, gaya struk impor)
    "Rp 1.250.500"-> 1250500
    "12.50"       -> 12.5    (titik = desimal, 2 digit di belakang)
    "1.234,56"    -> 1234.56 (format Eropa/Indonesia lengkap)
"""

from __future__ import annotations

import json
import re

_NUMBER_CHARS = re.compile(r"[^0-9.,\-]")


def parse_amount(value: object) -> float | None:
    """Ubah teks harga menjadi float. Kembalikan None kalau tidak bisa dibaca."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    # tanda kurung atau minus di mana saja dianggap angka negatif (biasanya diskon)
    negative = text.startswith("(") or "-" in text
    text = _NUMBER_CHARS.sub("", text).replace("-", "")
    if not re.search(r"\d", text):
        return None

    last_dot, last_comma = text.rfind("."), text.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        # dua jenis pemisah muncul: yang paling belakang adalah desimal
        decimal_sep = "." if last_dot > last_comma else ","
        thousand_sep = "," if decimal_sep == "." else "."
        text = text.replace(thousand_sep, "").replace(decimal_sep, ".")
    elif last_dot >= 0 or last_comma >= 0:
        sep = "." if last_dot >= 0 else ","
        parts = text.split(sep)
        # "25.000" / "1.250.000" -> semua grup setelah pemisah panjangnya 3 digit
        is_thousand = len(parts) > 2 or len(parts[-1]) == 3
        text = (
            text.replace(sep, "")
            if is_thousand
            else text.replace(sep, ".")
        )

    try:
        number = float(text)
    except ValueError:
        return None

    return -number if negative else number


def parse_quantity(value: object, default: float = 1) -> float:
    """Baca jumlah item, contoh: "2", "2x", "x2", "2 pcs"."""
    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value) if value > 0 else default

    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    if not match:
        return default

    qty = float(match.group().replace(",", "."))
    return qty if qty > 0 else default


def extract_json(text: str) -> dict:
    """Ambil objek JSON pertama dari output model.

    VLM kadang membungkus jawabannya dengan ```json ... ``` atau menambahkan
    kalimat pembuka, jadi kita cari kurung kurawal terluar.
    """
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("Output model tidak mengandung JSON.")

    return json.loads(cleaned[start : end + 1])
