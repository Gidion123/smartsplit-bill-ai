"""Langkah 3: isi nama peserta dan pilih siapa yang membayar tiap item."""

from __future__ import annotations

import streamlit as st

from ..schema import Receipt
from . import state
from .components import nav_buttons
from .formatting import format_money, format_qty


def render(currency: str) -> None:
    receipt = state.get_receipt()
    if receipt is None or not receipt.items:
        state.go_to(0)
        st.rerun()

    _participants_section()
    participants = st.session_state.participants
    if not participants:
        st.info("Tambahkan minimal satu nama peserta untuk mulai membagi item.")
        nav_buttons(back_step=1, key="assign_empty")
        return

    st.divider()
    _prune_assignment(receipt, participants)
    assigned_count = _items_section(receipt, participants, currency)

    total_items = len(receipt.items)
    st.progress(assigned_count / total_items, text=f"{assigned_count} dari {total_items} item sudah ada pembayarnya")
    if nav_buttons(
        back_step=1,
        next_label="Hitung tagihan →",
        next_disabled=assigned_count < total_items,
        key="assign",
    ):
        state.go_to(3)
        st.rerun()


# ---------------------------------------------------------------- peserta
def _participants_section() -> None:
    st.subheader("Siapa saja yang ikut patungan?")
    with st.form("add_participants", clear_on_submit=True, border=False):
        input_col, button_col = st.columns([4, 1], vertical_alignment="bottom")
        raw_names = input_col.text_input(
            "Nama peserta",
            placeholder="Contoh: Andi, Budi, Citra",
            help="Bisa langsung beberapa nama sekaligus, pisahkan dengan koma.",
            key="participant_name_input",
        )
        submitted = button_col.form_submit_button("Tambah", width="stretch")

    if submitted and raw_names.strip():
        _add_participants(raw_names)
        st.rerun()

    participants = st.session_state.participants
    if participants:
        # klik nama untuk menghapus peserta
        removed = st.pills(
            "Peserta (klik nama untuk menghapus)",
            options=participants,
            format_func=lambda name: f"{name}  ✕",
            key=f"remove_participant_{st.session_state.assign_version}",
        )
        if removed:
            participants.remove(removed)
            st.session_state.assign_version += 1
            st.rerun()


def _add_participants(raw_names: str) -> None:
    existing = {name.lower() for name in st.session_state.participants}
    for name in raw_names.split(","):
        name = " ".join(name.split())  # rapikan spasi ganda
        if name and name.lower() not in existing:
            st.session_state.participants.append(name)
            existing.add(name.lower())
    st.session_state.assign_version += 1


# ---------------------------------------------------------------- item
def _items_section(receipt: Receipt, participants: list[str], currency: str) -> int:
    title_col, action_col = st.columns([3, 2], vertical_alignment="bottom")
    title_col.subheader("Pilih pembayar tiap item")
    if action_col.button(
        "Item yang belum dipilih → bagi rata ke semua",
        width="stretch",
        help="Cocok untuk item yang dimakan bersama, misal nasi bakul atau air mineral.",
    ):
        for idx in range(len(receipt.items)):
            if not st.session_state.assignment.get(idx):
                st.session_state.assignment[idx] = {name: 1.0 for name in participants}
        st.session_state.assign_version += 1
        st.rerun()

    version = st.session_state.assign_version
    assigned = 0
    for idx, item in enumerate(receipt.items):
        current = st.session_state.assignment.get(idx, {})
        with st.container(border=True):
            info_col, payer_col = st.columns([2, 3])
            info_col.markdown(f"**{item.name}**")
            info_col.caption(
                f"{format_qty(item.quantity)} × {format_money(item.unit_price or item.total_price, currency)}"
                f" = {format_money(item.total_price, currency)}"
            )
            selected = payer_col.multiselect(
                "Dibayar oleh",
                options=participants,
                default=list(current),
                placeholder="Pilih satu atau beberapa orang",
                key=f"payers_{idx}_{version}",
                label_visibility="collapsed",
            )
            portions = _portion_inputs(idx, item.total_price, selected, current, currency, payer_col)

        st.session_state.assignment[idx] = portions
        if portions:
            assigned += 1
    return assigned


def _portion_inputs(idx, price, selected, current, currency, container) -> dict[str, float]:
    """Kalau item dibagi beberapa orang, default-nya rata. User bisa atur porsi berbeda,
    misal 3 tusuk sate: Andi 2 porsi, Budi 1 porsi."""
    if len(selected) <= 1:
        return {name: 1.0 for name in selected}

    version = st.session_state.assign_version
    custom = container.toggle("Porsi tidak rata", key=f"custom_{idx}_{version}",
                              value=len(set(current.values())) > 1)
    if not custom:
        share = price / len(selected)
        container.caption(f"Dibagi rata: {format_money(share, currency)} per orang")
        return {name: 1.0 for name in selected}

    cols = container.columns(len(selected))
    portions = {}
    for col, name in zip(cols, selected):
        portions[name] = col.number_input(
            name, min_value=0.0, step=1.0, value=float(current.get(name, 1.0)),
            key=f"portion_{idx}_{name}_{version}",
        )
    total_portion = sum(portions.values())
    if total_portion <= 0:
        container.warning("Total porsi tidak boleh 0.")
        return {}
    container.caption(
        " · ".join(f"{n}: {format_money(price * p / total_portion, currency)}" for n, p in portions.items())
    )
    return {n: p for n, p in portions.items() if p > 0}


def _prune_assignment(receipt: Receipt, participants: list[str]) -> None:
    """Buang pilihan yang sudah tidak valid (peserta dihapus / item dihapus di langkah 2)."""
    valid = set(participants)
    cleaned = {}
    for idx, portions in st.session_state.assignment.items():
        if idx < len(receipt.items):
            kept = {n: p for n, p in portions.items() if n in valid}
            if kept:
                cleaned[idx] = kept
    st.session_state.assignment = cleaned
