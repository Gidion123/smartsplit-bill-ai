"""
Logika pembagian tagihan (split bill).

Aturan yang dipakai:
1. Harga item dibagi ke orang yang dipilih. Kalau satu item dipilih beberapa
   orang, harga dibagi sesuai porsi (default porsi sama rata).
2. Biaya tambahan (pajak, service, diskon, dll.) dibagi PROPORSIONAL terhadap
   subtotal item masing-masing orang. Jadi yang pesan lebih banyak, menanggung
   pajak lebih besar. Ini cara yang paling adil dan umum dipakai.
3. Hasil akhir dibulatkan ke satuan mata uang terkecil dengan metode
   "largest remainder" sehingga jumlah semua orang PASTI sama dengan total bill
   (tidak ada selisih 1 rupiah yang hilang karena pembulatan).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .schema import Receipt


@dataclass
class ItemShare:
    item_name: str
    portion: float  # porsi orang ini untuk item tsb (0-1)
    amount: float


@dataclass
class PersonBill:
    name: str
    items: list[ItemShare] = field(default_factory=list)
    subtotal: float = 0.0
    charges: dict[str, float] = field(default_factory=dict)
    total: float = 0.0  # sudah dibulatkan

    @property
    def charges_sum(self) -> float:
        return sum(self.charges.values())


@dataclass
class SplitResult:
    people: list[PersonBill]
    bill_total: float

    @property
    def people_total(self) -> float:
        return sum(person.total for person in self.people)

    @property
    def is_balanced(self) -> bool:
        return abs(self.people_total - self.bill_total) < 1e-6


class SplitError(ValueError):
    """Dilempar kalau data assignment belum lengkap/valid."""


# Assignment: index item -> {nama peserta: porsi}. Contoh:
# {0: {"Andi": 1}, 1: {"Andi": 1, "Budi": 1}}  -> item ke-1 dibagi dua rata.
Assignment = dict[int, dict[str, float]]


def split_bill(
    receipt: Receipt,
    participants: list[str],
    assignment: Assignment,
    decimals: int = 0,
) -> SplitResult:
    """Hitung tagihan tiap orang berdasarkan pilihan item."""
    if not participants:
        raise SplitError("Belum ada peserta.")
    _validate_assignment(receipt, participants, assignment)

    bills = {name: PersonBill(name=name) for name in participants}

    # 1) bagi harga item
    for idx, item in enumerate(receipt.items):
        portions = {n: p for n, p in assignment[idx].items() if p > 0}
        total_portion = sum(portions.values())
        for name, portion in portions.items():
            ratio = portion / total_portion
            amount = item.total_price * ratio
            bills[name].items.append(ItemShare(item.name, ratio, amount))
            bills[name].subtotal += amount

    # 2) bagi biaya tambahan secara proporsional
    items_total = sum(b.subtotal for b in bills.values())
    for charge in receipt.charges:
        for bill in bills.values():
            if items_total > 0:
                weight = bill.subtotal / items_total
            else:
                weight = 1 / len(bills)
            bill.charges[charge.name] = bill.charges.get(charge.name, 0) + charge.amount * weight

    # 3) bulatkan dan pastikan jumlahnya sama persis dengan total bill
    bill_total = receipt.total if receipt.total is not None else items_total + receipt.charges_sum
    exact = [b.subtotal + b.charges_sum for b in bills.values()]
    rounded = allocate_rounding(exact, bill_total, decimals)
    for bill, value in zip(bills.values(), rounded):
        bill.total = value

    return SplitResult(people=list(bills.values()), bill_total=round(bill_total, decimals))


def allocate_rounding(values: list[float], target: float, decimals: int = 0) -> list[float]:
    """Bulatkan list angka supaya jumlahnya tepat `target` (largest remainder).

    Contoh: 100 dibagi 3 orang -> [33.33, 33.33, 33.33]. Pembulatan biasa
    menghasilkan 99, jadi 1 rupiah sisanya diberikan ke orang dengan sisa
    desimal terbesar -> [34, 33, 33].
    """
    scale = 10**decimals
    target_units = round(target * scale)
    scaled = [v * scale for v in values]
    floors = [int(_floor(v)) for v in scaled]
    remainder = target_units - sum(floors)

    # urutkan berdasarkan pecahan terbesar; kalau remainder negatif ambil dari yang terkecil
    order = sorted(range(len(values)), key=lambda i: scaled[i] - floors[i], reverse=True)
    step = 1 if remainder >= 0 else -1
    if remainder < 0:
        order.reverse()
    for k in range(abs(remainder)):
        floors[order[k % len(order)]] += step
    return [units / scale for units in floors]


def _floor(value: float) -> float:
    # toleransi kecil agar 33.9999999 (error floating point) tetap dibaca 34
    return math.floor(value + 1e-9)


def _validate_assignment(receipt: Receipt, participants: list[str], assignment: Assignment) -> None:
    unassigned = []
    for idx, item in enumerate(receipt.items):
        portions = assignment.get(idx) or {}
        if sum(p for p in portions.values() if p > 0) <= 0:
            unassigned.append(item.name)
            continue
        unknown = set(portions) - set(participants)
        if unknown:
            raise SplitError(f"Peserta tidak dikenal: {', '.join(sorted(unknown))}")
    if unassigned:
        raise SplitError("Item belum ada yang bayar: " + ", ".join(unassigned))
