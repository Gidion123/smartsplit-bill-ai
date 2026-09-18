"""Langkah 1: upload foto nota lalu baca dengan AI."""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st
from PIL import Image

from ..readers import ReaderError, create_reader
from ..readers.base import prepare_image
from ..readers.registry import APP_READER_KEY
from ..schema import Receipt
from . import state
from .sidebar import Settings

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]


@st.cache_resource(show_spinner=False)
def load_reader(api_key: str | None, model_name: str):
    """Reader di-cache per (api_key, model) supaya client API tidak dibuat ulang tiap klik."""
    return create_reader(APP_READER_KEY, api_key=api_key, model_name=model_name)


def render(settings: Settings) -> None:
    source_col, preview_col = st.columns([3, 2], gap="large")

    with source_col:
        st.subheader("Upload foto nota")
        upload_tab, camera_tab, sample_tab = st.tabs(["Upload file", "Kamera", "Contoh nota"])
        with upload_tab:
            uploaded = st.file_uploader("Pilih gambar nota", type=IMAGE_TYPES)
            if uploaded is not None:
                _set_image(uploaded.getvalue(), Image.open(uploaded))
        with camera_tab:
            photo = st.camera_input("Foto nota langsung dari kamera")
            if photo is not None:
                _set_image(photo.getvalue(), Image.open(photo))
        with sample_tab:
            _sample_picker()

        st.markdown(" ")
        read_clicked = st.button(
            "Baca nota dengan AI",
            type="primary",
            disabled=st.session_state.image is None,
            width="stretch",
        )
        if st.button("Isi manual tanpa AI", width="stretch"):
            state.set_receipt(Receipt())
            st.session_state.read_meta = None
            state.go_to(1)
            st.rerun()

    with preview_col:
        if st.session_state.image is not None:
            st.image(st.session_state.image, caption="Pratinjau nota", width="stretch")
        else:
            st.info("Belum ada gambar. Pastikan foto nota fokus dan seluruh isi struk terlihat.")

    if read_clicked:
        _run_reader(settings)


def _set_image(raw_bytes: bytes, image: Image.Image) -> None:
    """Simpan gambar ke session. Kalau gambarnya baru, hasil bacaan lama dihapus."""
    image_id = hashlib.md5(raw_bytes).hexdigest()
    if st.session_state.image_id != image_id:
        st.session_state.image_id = image_id
        st.session_state.image = prepare_image(image)
        st.session_state.receipt = None
        st.session_state.read_meta = None


def _sample_picker() -> None:
    samples = sorted(p for p in SAMPLES_DIR.glob("*") if p.suffix.lower().lstrip(".") in IMAGE_TYPES)
    if not samples:
        st.caption("Folder `samples/` masih kosong.")
        return
    choice = st.selectbox("Pilih contoh", samples, format_func=lambda p: p.name, index=None)
    if choice is not None:
        _set_image(choice.read_bytes(), Image.open(choice))


def _run_reader(settings: Settings) -> None:
    try:
        with st.spinner("Menyiapkan reader..."):
            reader = load_reader(settings.api_key, settings.model_name)
        with st.spinner(f"{reader.label} sedang membaca nota..."):
            result = reader.read(st.session_state.image)
    except ReaderError as err:
        st.error(str(err))
        return
    except ImportError as err:
        st.error(f"Library belum terpasang: {err.name}. Cek README bagian instalasi.")
        return

    state.set_receipt(result.receipt)
    st.session_state.read_meta = {
        "model": result.model_label,
        "seconds": result.seconds,
        "raw": result.raw_output,
    }
    state.go_to(1)
    st.rerun()
