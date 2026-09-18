"""Sidebar pengaturan aplikasi.

Aplikasi hanya memakai satu reader (DeepSeek), dan konfigurasinya diambil
sepenuhnya dari file `.env`. Sidebar hanya **menampilkan status** konfigurasi
tersebut, tidak bisa diedit dari UI, supaya:

- API key tidak pernah diketik (apalagi ikut terekam) lewat layar aplikasi,
- `.env` tetap menjadi satu-satunya sumber konfigurasi.

Yang masih bisa diubah user hanyalah mata uang tampilan.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st

from ..readers.deepseek_reader import DEFAULT_DEEPSEEK_MODEL
from .formatting import CURRENCIES


@dataclass
class Settings:
    """Pengaturan yang dipakai halaman lain."""

    api_key: str | None
    model_name: str
    currency: str


def render_sidebar() -> Settings:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    model_name = os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)

    with st.sidebar:
        st.header("Pengaturan")

        st.markdown("**Model pembaca nota**")
        st.code(model_name, language=None)

        if api_key:
            st.success("DeepSeek API key terbaca dari file .env.", icon=":material/key:")
        else:
            st.error(
                "DEEPSEEK_API_KEY belum ada di file .env, jadi nota belum bisa dibaca. "
                "Isi file .env lalu jalankan ulang aplikasi.",
                icon=":material/key_off:",
            )

        currency = st.selectbox("Mata uang", list(CURRENCIES), index=0, key="currency")

        st.divider()
        st.caption(
            "Alur: upload nota → cek hasil bacaan AI → pilih siapa bayar item apa → "
            "lihat tagihan per orang. Pajak & service dibagi proporsional."
        )
        st.caption(
            "Model dipilih dari hasil riset di notebooks/01_Research.ipynb: "
            "DeepSeek paling seimbang antara akurasi, reliability, dan kecepatan."
        )

    return Settings(api_key=api_key, model_name=model_name, currency=currency)
