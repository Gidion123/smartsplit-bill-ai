"""Uji bagian DeepSeekReader yang bisa diuji tanpa memanggil API."""

import base64
import io

import pytest
from PIL import Image

pytest.importorskip("openai")

from modules.readers.deepseek_reader import DEFAULT_DEEPSEEK_MODEL, DeepSeekReader
from modules.readers.base import ReaderError


def test_tanpa_api_key_memberi_pesan_jelas(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ReaderError, match="DEEPSEEK_API_KEY"):
        DeepSeekReader()


def test_model_default_dipakai_kalau_env_kosong(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    reader = DeepSeekReader()
    assert reader.model_name == DEFAULT_DEEPSEEK_MODEL
    assert DEFAULT_DEEPSEEK_MODEL in reader.label


def test_model_dari_argumen_mengalahkan_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    monkeypatch.setenv("DEEPSEEK_MODEL", "dari-env")
    reader = DeepSeekReader(model_name="dari-argumen")
    assert reader.model_name == "dari-argumen"


def test_image_to_data_url_menghasilkan_jpeg_base64():
    url = DeepSeekReader._image_to_data_url(Image.new("RGB", (40, 60), "white"))
    assert url.startswith("data:image/jpeg;base64,")
    decoded = base64.b64decode(url.split(",", 1)[1])
    assert Image.open(io.BytesIO(decoded)).format == "JPEG"


def test_schema_receipt_punya_field_yang_dibutuhkan():
    schema = DeepSeekReader._receipt_schema()
    assert set(schema["properties"]) >= {"items", "subtotal", "charges", "total"}
