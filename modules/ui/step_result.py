"""Langkah 4: tampilkan total yang harus dibayar tiap orang."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..split import SplitError, SplitResult, split_bill
from . import state
from .components import nav_buttons
from .formatting import currency_decimals, format_money


def render(currency: str) -> None:
    receipt = state.get_receipt()
    try:
        result = split_bill(
            receipt,
            st.session_state.participants,
            st.session_state.assignment,
            decimals=currency_decimals(currency),
        )
    except SplitError as err:
        st.error(str(err))
        nav_buttons(back_step=2, key="result_error")
        return

    _summary_metrics(result, currency)
    _person_cards(result, currency)

    st.subheader("Rekap")
    st.dataframe(_summary_table(result, currency), hide_index=True, width="stretch")
    _share_section(result, receipt.merchant_name, currency)

    if nav_buttons(back_step=2, next_label="Nota baru", key="result"):
        state.reset_bill(keep_participants=True)
        st.rerun()


def _summary_metrics(result: SplitResult, currency: str) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total bill", format_money(result.bill_total, currency))
    c2.metric("Jumlah semua orang", format_money(result.people_total, currency))
    c3.metric("Peserta", len(result.people))
    if result.is_balanced:
        st.success("Cocok: jumlah tagihan semua orang sama persis dengan total bill.")
    else:  # seharusnya tidak pernah terjadi karena ada pembulatan largest remainder
        st.error("Jumlah tagihan tidak sama dengan total bill. Cek kembali data nota.")


def _person_cards(result: SplitResult, currency: str) -> None:
    per_row = 3
    for start in range(0, len(result.people), per_row):
        cols = st.columns(per_row)
        for col, person in zip(cols, result.people[start : start + per_row]):
            with col.container(border=True):
                st.markdown(f"**{person.name}**")
                st.markdown(
                    f'<div class="person-total">{format_money(person.total, currency)}</div>',
                    unsafe_allow_html=True,
                )
                if not person.items:
                    st.caption("Tidak memesan item apa pun.")
                    continue
                with st.expander("Rincian"):
                    for share in person.items:
                        portion = "" if share.portion == 1 else f" ({share.portion:.0%})"
                        st.markdown(f"- {share.item_name}{portion}: {format_money(share.amount, currency)}")
                    st.markdown(f"Subtotal item: **{format_money(person.subtotal, currency)}**")
                    for name, amount in person.charges.items():
                        st.markdown(f"- {name}: {format_money(amount, currency)}")


def _summary_table(result: SplitResult, currency: str) -> pd.DataFrame:
    rows = [
        {
            "Nama": p.name,
            "Subtotal item": format_money(p.subtotal, currency),
            "Pajak/service/diskon": format_money(p.charges_sum, currency),
            "Total bayar": format_money(p.total, currency),
        }
        for p in result.people
    ]
    return pd.DataFrame(rows)


def _share_section(result: SplitResult, merchant: str | None, currency: str) -> None:
    """Fitur tambahan: teks siap kirim ke grup WhatsApp + unduh CSV."""
    lines = [f"Split bill {merchant}" if merchant else "Split bill"]
    lines += [f"- {p.name}: {format_money(p.total, currency)}" for p in result.people]
    lines.append(f"Total: {format_money(result.bill_total, currency)}")
    text = "\n".join(lines)

    csv = pd.DataFrame(
        [
            {"nama": p.name, "subtotal_item": round(p.subtotal, 2),
             "biaya_tambahan": round(p.charges_sum, 2), "total": p.total}
            for p in result.people
        ]
    ).to_csv(index=False)

    text_col, file_col = st.columns([3, 1])
    with text_col:
        st.markdown("**Teks untuk dikirim ke grup** (klik ikon salin di kanan atas)")
        st.code(text, language=None)
    with file_col:
        st.markdown("**Unduh**")
        st.download_button("CSV rekap", csv, file_name="split_bill.csv", mime="text/csv", width="stretch")
