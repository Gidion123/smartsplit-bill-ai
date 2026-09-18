"""Kumpulan pembaca nota (receipt reader).

Aplikasi memakai DeepSeek (`APP_READER_KEY`). Donut dan Qwen tersedia untuk
mereproduksi benchmark riset di `research/benchmark.py`.
"""

from .base import ReaderError, ReadResult, ReceiptReader
from .registry import APP_READER_KEY, RESEARCH_READERS, create_reader

__all__ = [
    "APP_READER_KEY",
    "RESEARCH_READERS",
    "ReaderError",
    "ReadResult",
    "ReceiptReader",
    "create_reader",
]
