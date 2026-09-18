"""Langkah 2: user mengecek dan mengoreksi hasil bacaan AI.

AI tidak 100% akurat, jadi user WAJIB bisa mengedit sebelum tagihan dibagi.
Setiap perubahan langsung dicek konsistensinya (item vs subtotal vs total).
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from ..schema import ExtraCharge, Receipt, ReceiptItem
from ..validation import check_receipt, has_errors, reconcile_receipt
from . import state
from .components import nav_buttons
from .formatting import currency_decimals, format_money

ITEM_COLUMNS = {
    "name": st.column_config.TextColumn("Nama item", required=True, width="medium"),
    "quantity": st.column_config.NumberColumn("Jumlah", min_value=0, step=1, default=1),
    "unit_price": st.column_config.NumberColumn("Harga satuan", min_value=0, format="localized"),
    "total_price": st.column_config.NumberColumn("Total harga", min_value=0, format="localized"),
}
CHARGE_COLUMNS = {
    "name": st.column_config.TextColumn("Nama biaya", required=True, width="medium"),
    "amount": st.column_config.NumberColumn(
        "Nominal", format="localized", help="Diskon ditulis negatif, contoh -5000"
    ),
}


def render(currency: str) -> None:
    receipt = state.get_receipt()
    if receipt is None:
        state.go_to(0)
        st.rerun()

    meta = st.session_state.read_meta
    if meta:
        st.caption(f"Dibaca oleh **{meta['model']}** dalam **{meta['seconds']:.1f} detik**.")

    image_col, form_col = st.columns([2, 3], gap="large")
    with image_col:
        if st.session_state.image is not None:
            st.image(st.session_state.image, width="stretch")
        if meta:
            with st.expander("Output mentah model"):
                st.code(meta["raw"] or "(kosong)", language="json", wrap_lines=True)

    with form_col:
        edited = _receipt_form(st.session_state.editor_base or receipt, currency)
        issues = check_receipt(edited)
        _render_issues(issues, edited)

    # simpan hasil edit tanpa me-reset tabel (supaya kursor editor tidak lompat)
    state.set_receipt(edited, reset_editor=False)
    if nav_buttons(back_step=0, next_label="Lanjut →", next_disabled=has_errors(issues), key="review"):
        # widget editor dihapus Streamlit saat pindah halaman, jadi hasil edit
        # dijadikan data awal editor agar tidak hilang kalau user kembali ke sini
        state.set_receipt(edited)
        state.go_to(2)
        st.rerun()


def _receipt_form(receipt: Receipt, currency: str) -> Receipt:
    version = st.session_state.editor_version

    merchant = st.text_input("Nama toko", value=receipt.merchant_name or "", key=f"merchant_{version}")

    st.markdown("**Item belanja**")
    items_df = pd.DataFrame(
        [item.model_dump() for item in receipt.items], columns=list(ITEM_COLUMNS)
    )
    items_df = st.data_editor(
        items_df,
        column_config=ITEM_COLUMNS,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"items_editor_{version}",
    )
    items = _items_from_df(items_df)
    items_sum = sum(item.total_price for item in items)
    st.caption(f"Jumlah harga item: {format_money(items_sum, currency)}")

    st.markdown("**Biaya tambahan** (pajak, service, diskon, dll.)")
    charges_df = pd.DataFrame(
        [charge.model_dump() for charge in receipt.charges], columns=list(CHARGE_COLUMNS)
    )
    charges_df = st.data_editor(
        charges_df,
        column_config=CHARGE_COLUMNS,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"charges_editor_{version}",
    )
    charges = _charges_from_df(charges_df)

    number_format = f"%.{currency_decimals(currency)}f"
    sub_col, total_col = st.columns(2)
    subtotal = sub_col.number_input(
        "Subtotal", min_value=0.0, value=float(receipt.subtotal or 0), step=1000.0,
        format=number_format, key=f"subtotal_{version}",
    )
    total = total_col.number_input(
        "Total bill", min_value=0.0, value=float(receipt.total or 0), step=1000.0,
        format=number_format, key=f"total_{version}",
    )

    return Receipt(
        merchant_name=merchant or None,
        items=items,
        subtotal=subtotal,
        charges=charges,
        total=total,
    )


def _render_issues(issues, receipt: Receipt) -> None:
    if not issues:
        st.success("Angka di nota sudah konsisten: item = subtotal, subtotal + biaya = total.")
        return
    for issue in issues:
        (st.error if issue.level == "error" else st.warning)(issue.message)

    fix_col, recalc_col = st.columns(2)
    if fix_col.button(
        "Rapikan otomatis",
        help="Subtotal disamakan dengan jumlah item, selisih ke total dicatat sebagai 'Selisih / pembulatan'.",
        width="stretch",
    ):
        state.set_receipt(reconcile_receipt(receipt))
        st.rerun()
    if recalc_col.button(
        "Hitung ulang total per item",
        help="Total harga tiap item = jumlah × harga satuan.",
        width="stretch",
    ):
        fixed = receipt.model_copy(deep=True)
        for item in fixed.items:
            if item.unit_price:
                item.total_price = item.unit_price * item.quantity
        state.set_receipt(fixed)
        st.rerun()


def _items_from_df(df: pd.DataFrame) -> list[ReceiptItem]:
    items = []
    for row in df.to_dict("records"):
        name = str(row.get("name") or "").strip()
        total_price = _to_number(row.get("total_price"))
        unit_price = _to_number(row.get("unit_price"))
        qty = _to_number(row.get("quantity")) or 1
        if total_price is None and unit_price is not None:
            total_price = unit_price * qty
        if not name and total_price is None:
            continue  # baris kosong baru yang belum diisi
        items.append(
            ReceiptItem(name=name, quantity=qty, unit_price=unit_price, total_price=total_price or 0)
        )
    return items


def _charges_from_df(df: pd.DataFrame) -> list[ExtraCharge]:
    charges = []
    for row in df.to_dict("records"):
        amount = _to_number(row.get("amount"))
        if amount is None:
            continue
        charges.append(ExtraCharge(name=str(row.get("name") or "Biaya lain"), amount=amount))
    return charges


def _to_number(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)
