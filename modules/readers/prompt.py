"""Prompt yang dipakai bersama oleh model VLM (DeepSeek & Qwen-VL).

Prompt dibuat sama persis untuk kedua model supaya perbandingannya adil.
"""

RECEIPT_PROMPT = """
Kamu adalah sistem pembaca struk belanja. Baca gambar struk ini dan kembalikan
HANYA JSON (tanpa penjelasan) dengan format:

{
  "merchant_name": "nama toko atau null",
  "items": [
    {"name": "nama item", "quantity": 1, "unit_price": 10000, "total_price": 10000}
  ],
  "subtotal": 10000,
  "charges": [
    {"name": "Pajak 10%", "amount": 1000}
  ],
  "total": 11000
}

Aturan:
- Semua harga ditulis sebagai angka polos tanpa "Rp", titik, atau koma ribuan.
  Contoh: "25.000" ditulis 25000.
- quantity = 1 jika jumlah tidak tertulis.
- total_price = total harga baris item (quantity x unit_price).
- subtotal = jumlah harga semua item sebelum pajak/service/diskon.
- charges berisi semua biaya di antara subtotal dan total: pajak/PB1/PPN, service
  charge, diskon, pembulatan, ongkir, dll. Diskon ditulis NEGATIF.
- Jangan masukkan baris pembayaran seperti Tunai/Cash, Kembali/Change, atau
  Debit/QRIS ke dalam items maupun charges.
- total = grand total yang harus dibayar.
""".strip()
