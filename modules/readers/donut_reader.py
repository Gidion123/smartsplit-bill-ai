"""
Pembaca nota berbasis Donut (OCR-free Document Understanding Transformer).

Model: naver-clova-ix/donut-base-finetuned-cord-v2
- Encoder Swin Transformer membaca gambar, decoder BART langsung menghasilkan
  token terstruktur, tanpa tahap OCR terpisah.
- Sudah di-finetune pada dataset CORD (struk Indonesia), sehingga output-nya
  mengikuti label CORD: menu.nm, menu.cnt, menu.price, sub_total, total, dst.
- Ukuran ~200M parameter, masih masuk akal dijalankan di CPU.
"""

from __future__ import annotations

import re

from PIL import Image

from ..parsing import parse_amount, parse_quantity
from ..schema import ExtraCharge, Receipt, ReceiptItem
from .base import ReceiptReader
from .device import pick_device

DONUT_MODEL_ID = "naver-clova-ix/donut-base-finetuned-cord-v2"
TASK_PROMPT = "<s_cord-v2>"

# field biaya tambahan di bagian sub_total CORD -> nama yang ditampilkan
CORD_CHARGE_FIELDS = {
    "tax_price": "Pajak",
    "service_price": "Service charge",
    "othersvc_price": "Biaya lain",
    "discount_price": "Diskon",
    "etc": "Lain-lain",
}


class DonutReader(ReceiptReader):
    label = "Donut (CORD-v2)"

    def __init__(self, model_id: str = DONUT_MODEL_ID, device: str | None = None) -> None:
        from transformers import DonutProcessor, VisionEncoderDecoderModel

        self.device = device or pick_device()
        self.processor = DonutProcessor.from_pretrained(model_id)
        self.model = VisionEncoderDecoderModel.from_pretrained(model_id).to(self.device)
        self.model.eval()

    def _predict(self, image: Image.Image) -> tuple[Receipt, str]:
        import torch

        tokenizer = self.processor.tokenizer
        pixel_values = self.processor(image, return_tensors="pt").pixel_values.to(self.device)
        decoder_input_ids = tokenizer(
            TASK_PROMPT, add_special_tokens=False, return_tensors="pt"
        ).input_ids.to(self.device)

        with torch.inference_mode():
            output = self.model.generate(
                pixel_values,
                decoder_input_ids=decoder_input_ids,
                max_length=self.model.decoder.config.max_position_embeddings,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                use_cache=True,
                num_beams=1,  # greedy decoding, paling cepat
                bad_words_ids=[[tokenizer.unk_token_id]],
            )

        sequence = self.processor.batch_decode(output)[0]
        sequence = sequence.replace(tokenizer.eos_token, "").replace(tokenizer.pad_token, "")
        sequence = re.sub(r"<.*?>", "", sequence, count=1).strip()  # buang task prompt
        parsed = self.processor.token2json(sequence)
        return cord_to_receipt(parsed), sequence


def cord_to_receipt(data: dict) -> Receipt:
    """Petakan output format CORD ke skema `Receipt` aplikasi."""
    menus = data.get("menu") or []
    if isinstance(menus, dict):  # kalau hanya 1 item, Donut mengembalikan dict
        menus = [menus]

    items = []
    for menu in menus:
        if not isinstance(menu, dict):
            continue
        name = _first_text(menu.get("nm"))
        qty = parse_quantity(_first_text(menu.get("cnt")))
        unit_price = parse_amount(_first_text(menu.get("unitprice")))
        total_price = parse_amount(_first_text(menu.get("price")))
        if total_price is None and unit_price is not None:
            total_price = unit_price * qty
        if name and total_price is not None:
            items.append(
                ReceiptItem(name=name, quantity=qty, unit_price=unit_price, total_price=total_price)
            )

    sub_total = _as_dict(data.get("sub_total"))
    total_block = _as_dict(data.get("total"))

    charges = []
    for field, label in CORD_CHARGE_FIELDS.items():
        amount = parse_amount(_first_text(sub_total.get(field)))
        if amount:
            if field == "discount_price":
                amount = -abs(amount)
            charges.append(ExtraCharge(name=label, amount=amount))

    return Receipt(
        items=items,
        subtotal=parse_amount(_first_text(sub_total.get("subtotal_price"))),
        charges=charges,
        total=parse_amount(_first_text(total_block.get("total_price"))),
    )


def _first_text(value: object) -> str | None:
    """Field CORD bisa berupa string, list, atau dict bersarang; ambil teks pertama."""
    if value is None:
        return None
    if isinstance(value, list):
        return _first_text(value[0]) if value else None
    if isinstance(value, dict):
        return _first_text(next(iter(value.values()), None))
    return str(value).strip() or None


def _as_dict(value: object) -> dict:
    if isinstance(value, list):
        value = value[0] if value else {}
    return value if isinstance(value, dict) else {}
