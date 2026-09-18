"""
Pembaca nota berbasis Qwen-VL (Vision Language Model open-source, jalan lokal).

Default: Qwen/Qwen3-VL-2B-Instruct
- VLM umum (bukan khusus struk), jadi cara pakainya sama seperti VLM generatif lain:
  gambar + prompt -> JSON. Bedanya model ini jalan di komputer sendiri
  (data nota tidak keluar ke server pihak ketiga, tidak ada biaya API).
- Bisa diganti ke model Qwen lain lewat env `QWEN_MODEL_ID`,
  misal `Qwen/Qwen2.5-VL-3B-Instruct`.

ALUR:
    PIL Image
        ↓
    resize_max_side()
        ↓
    RECEIPT_PROMPT + image
        ↓
    Qwen Processor
        ↓
    model.generate()
        ↓
    decode output model
        ↓
    extract_json()
        ↓
    coerce_receipt()
        ↓
    Receipt

GENERATION:
    Qwen3-VL-2B-Instruct secara default menggunakan sampling:

        do_sample=True
        temperature=0.7
        top_p=0.8
        top_k=20

    Konfigurasi ini dipertahankan agar generation mengikuti perilaku
    bawaan model dan mengurangi risiko degeneration/repetition yang
    ditemukan ketika memakai greedy decoding pada beberapa receipt.

DEBUGGING:
    Jika output Qwen tidak bisa diubah menjadi JSON Receipt,
    error akan menampilkan:
    - pesan parser asli,
    - jumlah token output,
    - apakah output mencapai MAX_NEW_TOKENS,
    - bagian awal output,
    - bagian akhir output.

    Informasi tersebut digunakan untuk membedakan apakah kegagalan
    disebabkan oleh output yang terpotong, repetition loop,
    atau JSON yang memang malformed.
"""

from __future__ import annotations

import os

from PIL import Image

from ..parsing import extract_json
from ..schema import Receipt
from ..validation import coerce_receipt
from .base import ReaderError, ReceiptReader, resize_max_side
from .device import pick_device
from .prompt import RECEIPT_PROMPT


DEFAULT_QWEN_MODEL = "Qwen/Qwen3-VL-2B-Instruct"

# Jumlah token visual Qwen sebanding dengan resolusi gambar.
# 1024px adalah kompromi: teks struk masih terbaca, inference tidak terlalu berat.
MAX_IMAGE_SIDE = int(
    os.getenv(
        "QWEN_MAX_IMAGE_SIDE",
        "1024",
    )
)

# Batas maksimum token jawaban model.
# Untuk sementara tetap 1024 agar eksperimen fokus pada perubahan decoding.
MAX_NEW_TOKENS = 1024

# Generation config mengikuti konfigurasi bawaan resmi
# Qwen3-VL-2B-Instruct.
QWEN_TEMPERATURE = 0.7
QWEN_TOP_P = 0.8
QWEN_TOP_K = 20


class QwenVLReader(ReceiptReader):
    """Receipt reader lokal menggunakan Qwen Vision-Language Model."""

    def __init__(
        self,
        model_id: str | None = None,
        device: str | None = None,
    ) -> None:
        import torch
        from transformers import (
            AutoModelForImageTextToText,
            AutoProcessor,
        )

        self.model_id = (
            model_id
            or os.getenv(
                "QWEN_MODEL_ID",
                DEFAULT_QWEN_MODEL,
            )
        )

        self.label = (
            f"Qwen-VL "
            f"({self.model_id.split('/')[-1]})"
        )

        self.device = (
            device
            or pick_device()
        )

        # bfloat16 menghemat memori ~50% dibanding float32
        # (2B param: ~4GB vs ~8GB).
        self.processor = AutoProcessor.from_pretrained(
            self.model_id
        )

        self.model = (
            AutoModelForImageTextToText
            .from_pretrained(
                self.model_id,
                dtype=torch.bfloat16,
            )
        )

        self.model.to(
            self.device
        ).eval()

    def _predict(
        self,
        image: Image.Image,
    ) -> tuple[Receipt, str]:
        """Lakukan satu inference Qwen untuk satu gambar nota."""

        import torch

        # Batasi resolusi agar penggunaan visual token tetap terkontrol.
        image = resize_max_side(
            image,
            MAX_IMAGE_SIDE,
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": image,
                    },
                    {
                        "type": "text",
                        "text": RECEIPT_PROMPT,
                    },
                ],
            }
        ]

        # Ubah image + prompt ke format input Qwen.
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(
            self.device
        )

        # Gunakan sampling sesuai generation config bawaan
        # Qwen3-VL-2B-Instruct.
        with torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=True,
                temperature=QWEN_TEMPERATURE,
                top_p=QWEN_TOP_P,
                top_k=QWEN_TOP_K,
            )

        # Buang token prompt, sisakan jawaban model saja.
        answer_ids = generated[
            :,
            inputs["input_ids"].shape[1] :
        ]

        raw = self.processor.batch_decode(
            answer_ids,
            skip_special_tokens=True,
        )[0]

        # Informasi diagnostik untuk mengetahui apakah output
        # berhenti karena mencapai batas token.
        generated_tokens = answer_ids.shape[1]

        hit_token_limit = (
            generated_tokens
            >= MAX_NEW_TOKENS
        )

        try:
            return (
                coerce_receipt(
                    extract_json(raw)
                ),
                raw,
            )

        except ValueError as err:
            raise ReaderError(
                "Output Qwen bukan JSON yang valid.\n"
                f"Parser error: {err}\n"
                f"Generated tokens: {generated_tokens}\n"
                f"MAX_NEW_TOKENS: {MAX_NEW_TOKENS}\n"
                f"Hit max_new_tokens: {hit_token_limit}\n\n"
                f"Awal output:\n{raw[:300]!r}\n\n"
                f"Akhir output:\n{raw[-500:]!r}"
            ) from err
