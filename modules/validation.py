"""
Normalisasi dan pengecekan konsistensi data nota.

Output model tidak selalu lengkap/benar. Di sini kita:
1. `coerce_receipt`  : ubah dict "longgar" (hasil JSON model) jadi `Receipt`.
2. `normalize_receipt`: lengkapi field yang kosong (harga satuan, subtotal, total).
3. `check_receipt`   : cek hitungan nota, hasilnya ditampilkan ke user sebagai
   peringatan supaya user tahu bagian mana yang perlu dikoreksi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .parsing import parse_amount, parse_quantity
from .schema import ExtraCharge, Receipt, ReceiptItem

# selisih <= 1 rupiah dianggap sama (efek pembulatan)
TOLERANCE = 1.0


@dataclass
class Issue:
    level: Literal["error", "warning"]
    message: str


def coerce_receipt(data: dict) -> Receipt:
    """Bangun `Receipt` dari dict dengan nilai yang mungkin masih berupa teks."""
    items = []

    for raw in data.get("items") or []:
        name = str(raw.get("name") or "").strip()
        total_price = parse_amount(raw.get("total_price"))
        unit_price = parse_amount(raw.get("unit_price"))
        qty = parse_quantity(raw.get("quantity"))

        if total_price is None and unit_price is not None:
            total_price = unit_price * qty

        if not name or total_price is None:
            continue  # baris tanpa nama/harga tidak bisa dipakai untuk split

        items.append(
            ReceiptItem(
                name=name,
                quantity=qty,
                unit_price=unit_price,
                total_price=total_price,
            )
        )

    charges = []

    for raw in data.get("charges") or []:
        amount = parse_amount(raw.get("amount"))

        if amount is None or amount == 0:
            continue

        charges.append(
            ExtraCharge(
                name=str(raw.get("name") or "Biaya lain"),
                amount=amount,
            )
        )

    return Receipt(
        merchant_name=data.get("merchant_name"),
        items=items,
        subtotal=parse_amount(data.get("subtotal")),
        charges=charges,
        total=parse_amount(data.get("total")),
    )


def normalize_receipt(receipt: Receipt) -> Receipt:
    """Lengkapi nilai kosong tanpa mengubah angka yang sudah dibaca model."""
    receipt = receipt.model_copy(deep=True)

    for item in receipt.items:
        if item.quantity <= 0:
            item.quantity = 1

        if item.unit_price is None:
            item.unit_price = round(
                item.total_price / item.quantity,
                2,
            )

    # banyak struk menulis diskon tanpa tanda minus -> paksa negatif
    for charge in receipt.charges:
        if _looks_like_discount(charge.name) and charge.amount > 0:
            charge.amount = -charge.amount

    if receipt.subtotal is None:
        receipt.subtotal = receipt.items_sum

    if receipt.total is None:
        receipt.total = receipt.subtotal + receipt.charges_sum

    return receipt


def check_receipt(receipt: Receipt) -> list[Issue]:
    """Cek apakah angka-angka di nota saling konsisten."""
    issues: list[Issue] = []

    if not receipt.items:
        issues.append(
            Issue(
                "error",
                "Belum ada item. Tambahkan minimal satu item.",
            )
        )
        return issues

    for item in receipt.items:
        if not item.name.strip():
            issues.append(
                Issue(
                    "error",
                    "Ada item tanpa nama.",
                )
            )

        if item.total_price < 0:
            issues.append(
                Issue(
                    "error",
                    f"Harga '{item.name}' bernilai negatif.",
                )
            )

        if item.unit_price is not None:
            expected = item.unit_price * item.quantity

            if abs(expected - item.total_price) > TOLERANCE:
                issues.append(
                    Issue(
                        "warning",
                        f"'{item.name}': {item.quantity:g} x {item.unit_price:,.0f} "
                        f"≠ {item.total_price:,.0f}. Cek jumlah atau harganya.",
                    )
                )

    subtotal = receipt.subtotal or 0
    total = receipt.total or 0

    if abs(receipt.items_sum - subtotal) > TOLERANCE:
        issues.append(
            Issue(
                "error",
                f"Jumlah harga item ({receipt.items_sum:,.0f}) tidak sama dengan "
                f"subtotal ({subtotal:,.0f}).",
            )
        )

    if abs(subtotal + receipt.charges_sum - total) > TOLERANCE:
        issues.append(
            Issue(
                "error",
                f"Subtotal + biaya tambahan "
                f"({subtotal + receipt.charges_sum:,.0f}) "
                f"tidak sama dengan total ({total:,.0f}).",
            )
        )

    if total <= 0:
        issues.append(
            Issue(
                "error",
                "Total bill harus lebih dari 0.",
            )
        )

    return issues


def reconcile_receipt(receipt: Receipt) -> Receipt:
    """Perbaikan cepat: samakan subtotal dengan jumlah item dan catat selisih total
    sebagai baris 'Selisih / pembulatan' supaya nota kembali konsisten."""
    receipt = receipt.model_copy(deep=True)
    receipt.subtotal = receipt.items_sum
    gap = (receipt.total or 0) - receipt.subtotal - receipt.charges_sum

    if abs(gap) > TOLERANCE:
        receipt.charges.append(
            ExtraCharge(
                name="Selisih / pembulatan",
                amount=round(gap, 2),
            )
        )

    return receipt


def has_errors(issues: list[Issue]) -> bool:
    return any(issue.level == "error" for issue in issues)


def _looks_like_discount(name: str) -> bool:
    lowered = name.lower()

    return any(
        word in lowered
        for word in (
            "diskon",
            "discount",
            "disc",
            "potongan",
            "promo",
            "voucher",
        )
    )
