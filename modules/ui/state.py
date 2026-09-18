"""
Pengelolaan `st.session_state`.

Streamlit menjalankan ulang seluruh script setiap ada interaksi, jadi data yang
harus bertahan (gambar, hasil baca, peserta, dll.) disimpan di session_state.
Semua key dikumpulkan di sini supaya tidak ada typo nama key di file lain.
"""

from __future__ import annotations

import streamlit as st

from ..schema import Receipt

STEPS = ["Upload nota", "Cek data", "Bagi item", "Hasil"]

_DEFAULTS = {
    "step": 0,
    "image": None,  # PIL.Image nota yang diupload
    "image_id": None,  # penanda file, untuk tahu kalau user ganti gambar
    "read_meta": None,  # dict: model, detik, output mentah
    "receipt": None,  # Receipt yang sedang diedit/sudah dikonfirmasi
    "editor_base": None,  # Receipt awal yang ditampilkan di tabel editor
    "editor_version": 0,  # dinaikkan untuk me-reset tabel editor
    "participants": [],
    "assignment": {},  # {index item: {nama: porsi}}
    "assign_version": 0,  # dinaikkan saat daftar peserta berubah
}


def init_state() -> None:
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            # list/dict harus dicopy supaya default tidak ikut termodifikasi
            st.session_state[key] = value.copy() if isinstance(value, (list, dict)) else value


def go_to(step: int) -> None:
    st.session_state.step = max(0, min(step, len(STEPS) - 1))


def get_receipt() -> Receipt | None:
    return st.session_state.receipt


def set_receipt(receipt: Receipt, reset_editor: bool = True) -> None:
    """Simpan receipt. `reset_editor=True` berarti isi tabel editor diganti dengan
    receipt ini (dipakai setelah AI membaca atau setelah tombol perbaikan otomatis).

    Tabel editor sengaja selalu diberi data awal yang sama (`editor_base`); hasil
    ketikan user disimpan Streamlit di state widget. Kalau data awal ikut berubah
    setiap rerun, editor akan kehilangan perubahan yang sedang diketik.
    """
    st.session_state.receipt = receipt
    if reset_editor:
        st.session_state.editor_base = receipt
        st.session_state.editor_version += 1


def reset_bill(keep_participants: bool = True) -> None:
    """Mulai nota baru. Nama peserta dipertahankan karena biasanya grupnya sama."""
    participants = st.session_state.participants if keep_participants else []
    for key, value in _DEFAULTS.items():
        st.session_state[key] = value.copy() if isinstance(value, (list, dict)) else value
    st.session_state.participants = participants
