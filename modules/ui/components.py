"""Komponen tampilan kecil yang dipakai di beberapa halaman."""

from __future__ import annotations

import streamlit as st

from .state import STEPS


def render_header() -> None:
    st.markdown("## SmartSplit Bill")
    st.caption("Foto struknya, biar AI yang baca, lalu bagi tagihan dengan adil sampai ke rupiah terakhir.")


def render_stepper(current: int) -> None:
    """Indikator langkah di bagian atas halaman."""
    cols = st.columns(len(STEPS))
    for idx, (col, title) in enumerate(zip(cols, STEPS)):
        if idx < current:
            state_class, marker = "done", "✓"
        elif idx == current:
            state_class, marker = "active", str(idx + 1)
        else:
            state_class, marker = "todo", str(idx + 1)
        col.markdown(
            f'<div class="step {state_class}"><span>{marker}</span>{title}</div>',
            unsafe_allow_html=True,
        )


def nav_buttons(
    back_step: int | None = None,
    next_label: str | None = None,
    next_disabled: bool = False,
    key: str = "nav",
) -> bool:
    """Tombol kembali & lanjut. Mengembalikan True kalau tombol lanjut diklik."""
    left, _, right = st.columns([1, 3, 1])
    if back_step is not None and left.button("← Kembali", key=f"{key}_back", width="stretch"):
        st.session_state.step = back_step
        st.rerun()
    if next_label is None:
        return False
    return right.button(
        next_label, key=f"{key}_next", type="primary", disabled=next_disabled, width="stretch"
    )


CUSTOM_CSS = """
<style>
.step {display:flex; align-items:center; gap:.5rem; font-size:.9rem; color:#8a8f98;
       padding:.4rem 0; border-bottom:3px solid #e6e8eb;}
.step span {display:inline-flex; width:1.6rem; height:1.6rem; border-radius:50%;
            align-items:center; justify-content:center; background:#e6e8eb; font-weight:600;}
.step.active {color:inherit; font-weight:600; border-bottom-color:#0f9d7a;}
.step.active span {background:#0f9d7a; color:white;}
.step.done {border-bottom-color:#9fd9c8;}
.step.done span {background:#9fd9c8; color:#0b5d49;}
.person-total {font-size:1.6rem; font-weight:700; margin:.2rem 0 .6rem;}
</style>
"""
