"""
DeepSeek Receipt Reader
=======================

Module ini menangani pembacaan nota menggunakan
DeepSeek-V4.1-Flash melalui DeepSeek Vision API.

ALUR DATA:
    Input:
        PIL.Image
            │
            ▼
    resize_max_side()
            │
            ▼
    Convert Image → JPEG bytes
            │
            ▼
    JPEG bytes → Base64 Data URL
            │
            ▼
    DeepSeek API
        ├── gambar nota
        └── RECEIPT_PROMPT
            │
            ▼
    Structured JSON berdasarkan Receipt schema
            │
            ▼
    Pydantic validation
            │
            ▼
    Receipt object
            │
            ▼
    Return:
        (Receipt, raw_response)

KONFIGURASI:
    API key dan model tidak ditulis di source code.

    Keduanya berasal dari environment variable:

        DEEPSEEK_API_KEY
        DEEPSEEK_MODEL

    sehingga .env menjadi single source of truth
    untuk konfigurasi DeepSeek. Model juga dapat
    dikirim langsung dari sidebar aplikasi, dan
    DEFAULT_DEEPSEEK_MODEL dipakai sebagai fallback
    terakhir bila keduanya kosong.

ARSITEKTUR:
    DeepSeekReader mewarisi ReceiptReader sehingga memiliki
    interface yang sama dengan reader lain di project:

        DeepSeekReader   -> dipakai aplikasi
        DonutReader      -> hanya untuk benchmark riset
        QwenReader       -> hanya untuk benchmark riset

    Dengan demikian model dapat ditukar tanpa mengubah
    logika utama aplikasi.

VALIDASI:
    DeepSeek diminta menghasilkan JSON menggunakan
    JSON Schema yang dibuat langsung dari Pydantic model
    Receipt.

    Setelah response diterima, JSON tetap divalidasi
    kembali menggunakan Receipt.model_validate_json().

    Jika validasi langsung gagal, parser JSON existing
    project digunakan sebagai fallback:

        extract_json()
        coerce_receipt()

KEAMANAN:
    API key tidak pernah ditulis langsung di source code.
    API key hanya dibaca dari DEEPSEEK_API_KEY.
"""

from __future__ import annotations

import base64
import io
import os

from PIL import Image

from ..parsing import extract_json
from ..schema import Receipt
from ..validation import coerce_receipt
from .base import ReaderError, ReceiptReader, resize_max_side
from .prompt import RECEIPT_PROMPT


# Endpoint resmi DeepSeek yang kompatibel dengan OpenAI SDK.
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Model default kalau DEEPSEEK_MODEL tidak diisi di .env.
DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"

# Batas ukuran gambar sebelum dikirim ke API.
MAX_IMAGE_SIDE = 1600

# Output berupa JSON Receipt, jadi tidak membutuhkan output panjang.
MAX_OUTPUT_TOKENS = 4096


class DeepSeekReader(ReceiptReader):
    """Receipt reader menggunakan DeepSeek Vision API."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ReaderError(
                "Package 'openai' belum terinstall. "
                "Jalankan: pip install 'openai>=3.14,<4'"
            ) from exc

        # Gunakan argument eksplisit jika diberikan;
        # jika tidak, ambil dari environment.
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")

        if not api_key:
            raise ReaderError(
                "DEEPSEEK_API_KEY belum ditemukan. "
                "Tambahkan API key ke file .env."
            )

        self.model_name = (
            model_name
            or os.getenv("DEEPSEEK_MODEL")
            or DEFAULT_DEEPSEEK_MODEL
        )

        self.label = f"DeepSeek ({self.model_name})"

        self.client = OpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
        )

    @staticmethod
    def _image_to_data_url(image: Image.Image) -> str:
        """
        Mengubah PIL Image menjadi Base64 Data URL
        agar dapat dikirim sebagai image input ke API.
        """

        buffer = io.BytesIO()

        image.convert("RGB").save(
            buffer,
            format="JPEG",
            quality=90,
        )

        encoded = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        return f"data:image/jpeg;base64,{encoded}"

    @staticmethod
    def _receipt_schema() -> dict:
        """Mengambil JSON Schema langsung dari Pydantic Receipt."""

        return Receipt.model_json_schema()

    def _predict(
        self,
        image: Image.Image,
    ) -> tuple[Receipt, str]:
        """Melakukan satu inference DeepSeek untuk satu nota."""

        # Samakan preprocessing dengan reader lain di project.
        image = resize_max_side(
            image,
            MAX_IMAGE_SIDE,
        )

        image_data_url = self._image_to_data_url(image)

        response = self.client.responses.create(
            model=self.model_name,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": RECEIPT_PROMPT,
                        },
                        {
                            "type": "input_image",
                            "image_url": image_data_url,
                            "detail": "original",
                        },
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "receipt",
                    "schema": self._receipt_schema(),
                }
            },
            max_output_tokens=MAX_OUTPUT_TOKENS,
            reasoning={
                "effort": "none",
            },
        )

        raw = response.output_text or ""

        if not raw:
            raise ReaderError(
                "DeepSeek mengembalikan output kosong."
            )

        # Validasi utama: response harus sesuai Receipt.
        try:
            return Receipt.model_validate_json(raw), raw

        # Fallback menggunakan parser existing project.
        except ValueError:
            try:
                return coerce_receipt(
                    extract_json(raw)
                ), raw

            except ValueError as err:
                raise ReaderError(
                    "Jawaban DeepSeek bukan JSON Receipt "
                    f"yang valid: {raw[:300]}"
                ) from err
