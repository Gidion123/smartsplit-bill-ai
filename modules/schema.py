"""
Struktur data nota yang dipakai di seluruh aplikasi.

Semua model (DeepSeek, Donut, Qwen-VL) wajib mengembalikan data dengan bentuk
yang sama, yaitu `Receipt`. Dengan begitu bagian UI dan logika split bill
tidak perlu tahu model mana yang sedang dipakai.

Pydantic dipilih karena:
1. bisa menghasilkan JSON Schema untuk API yang mendukung structured output,
2. otomatis memvalidasi tipe data (misal harga harus angka).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReceiptItem(BaseModel):
    """Satu baris item belanja di nota."""

    name: str = Field(description="Nama item/menu persis seperti tertulis di nota.")
    quantity: float = Field(
        default=1,
        description="Jumlah item yang dibeli. Isi 1 jika tidak tertulis.",
    )
    unit_price: float | None = Field(
        default=None,
        description="Harga satuan per item, angka tanpa pemisah ribuan.",
    )
    total_price: float = Field(
        description="Total harga baris item ini (jumlah x harga satuan).",
    )


class ExtraCharge(BaseModel):
    """Biaya tambahan di luar item: pajak, service charge, diskon, pembulatan, dll.

    Diskon ditulis sebagai angka negatif supaya bisa langsung dijumlahkan.
    """

    name: str = Field(
        description="Nama biaya, contoh: PB1 10%, Service 5%, Diskon."
    )
    amount: float = Field(
        description="Nominal biaya. Diskon/potongan bernilai negatif."
    )


class Receipt(BaseModel):
    """Hasil pembacaan satu nota."""

    merchant_name: str | None = Field(
        default=None,
        description="Nama toko/restoran.",
    )
    items: list[ReceiptItem] = Field(default_factory=list)
    subtotal: float | None = Field(
        default=None,
        description="Jumlah semua item sebelum pajak/service/diskon.",
    )
    charges: list[ExtraCharge] = Field(default_factory=list)
    total: float | None = Field(
        default=None,
        description="Total akhir yang harus dibayar (grand total).",
    )

    @property
    def items_sum(self) -> float:
        return sum(item.total_price for item in self.items)

    @property
    def charges_sum(self) -> float:
        return sum(charge.amount for charge in self.charges)
