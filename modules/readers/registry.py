"""Daftar reader nota yang tersedia beserta cara membuatnya.

Pembagiannya:

- `APP_READER_KEY`
    Reader yang dipakai aplikasi Streamlit. Berdasarkan hasil riset di
    `notebooks/01_Research.ipynb`, aplikasi hanya memakai DeepSeek.

- `RESEARCH_READERS`
    Semua reader yang dipakai pada benchmark Step 1. Donut dan Qwen tetap
    disimpan di repo supaya hasil riset bisa direproduksi ulang, bukan karena
    dipakai aplikasi.
"""

from __future__ import annotations

from .base import ReceiptReader

# Reader utama aplikasi.
APP_READER_KEY = "deepseek"

# key internal -> label yang enak dibaca manusia
RESEARCH_READERS = {
    "deepseek": "DeepSeek (API)",
    "qwen": "Qwen3-VL 2B (lokal)",
    "donut": "Donut CORD-v2 (lokal)",
}


def create_reader(key: str, **kwargs) -> ReceiptReader:
    """Buat reader sesuai pilihan.

    Import dilakukan secara lazy agar dependency berat (torch, transformers)
    hanya dimuat ketika reader lokal benar-benar dipakai. Aplikasi yang hanya
    memakai DeepSeek tidak perlu menginstall torch sama sekali.
    """
    if key == "deepseek":
        from .deepseek_reader import DeepSeekReader

        return DeepSeekReader(**kwargs)

    if key == "donut":
        from .donut_reader import DonutReader

        return DonutReader(**kwargs)

    if key == "qwen":
        from .qwen_reader import QwenVLReader

        return QwenVLReader(**kwargs)

    raise ValueError(f"Model tidak dikenal: {key}")
