"""
Kelas dasar untuk semua pembaca nota.

Setiap model cukup mengimplementasikan `_predict(image) -> (Receipt, raw_text)`.
Pengukuran waktu, normalisasi, dan penanganan error disatukan di `read()`
supaya perbandingan kecepatan antar model adil (diukur dengan cara yang sama).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from PIL import Image, ImageOps

from ..schema import Receipt
from ..validation import normalize_receipt


class ReaderError(RuntimeError):
    """Error yang pesannya aman ditampilkan ke user."""


@dataclass
class ReadResult:
    receipt: Receipt  # sudah dinormalisasi, siap dipakai aplikasi
    parsed_receipt: Receipt  # murni hasil model sebelum dilengkapi (dipakai untuk evaluasi)
    raw_output: str  # output mentah model, berguna untuk debugging & analisis
    seconds: float  # waktu inference (tanpa waktu load model)
    model_label: str


class ReceiptReader(ABC):
    #: nama yang tampil di UI dan tabel benchmark
    label: str = "base"

    @abstractmethod
    def _predict(self, image: Image.Image) -> tuple[Receipt, str]:
        """Jalankan model dan kembalikan (receipt, output mentah)."""

    def read(self, image: Image.Image) -> ReadResult:
        image = prepare_image(image)
        start = time.perf_counter()
        try:
            receipt, raw = self._predict(image)
        except ReaderError:
            raise
        except Exception as err:  # error dari library pihak ketiga dibungkus
            raise ReaderError(f"{self.label} gagal membaca nota: {err}") from err
        elapsed = time.perf_counter() - start
        return ReadResult(normalize_receipt(receipt), receipt, raw, elapsed, self.label)


def prepare_image(image: Image.Image) -> Image.Image:
    """Rapikan gambar sebelum masuk model.

    Foto dari HP sering punya tag EXIF rotasi; tanpa `exif_transpose` gambar
    bisa terbaca miring. Model juga butuh mode RGB (bukan RGBA/PNG transparan).
    """
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def resize_max_side(image: Image.Image, max_side: int) -> Image.Image:
    """Perkecil gambar kalau sisi terpanjangnya melebihi `max_side`."""
    width, height = image.size
    scale = max_side / max(width, height)
    if scale >= 1:
        return image
    return image.resize(
        (int(width * scale), int(height * scale)),
        Image.Resampling.LANCZOS,
    )
