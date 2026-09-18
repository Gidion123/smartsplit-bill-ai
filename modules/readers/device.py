"""Pemilihan device untuk model lokal (CUDA / Apple Silicon MPS / CPU)."""

from __future__ import annotations

import os


def pick_device() -> str:
    """Pilih device terbaik yang tersedia.

    Bisa dipaksa lewat environment variable, misal `SMARTSPLIT_DEVICE=cpu`,
    berguna saat benchmark supaya kecepatan antar model dibandingkan di device yang sama.
    """
    forced = os.getenv("SMARTSPLIT_DEVICE")
    if forced:
        return forced

    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
