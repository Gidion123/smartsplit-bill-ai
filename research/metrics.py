"""
Metrik evaluasi hasil pembacaan nota dibanding ground truth (label manual).

Kenapa tidak cukup CER/WER saja? Untuk split bill yang penting bukan
teks mentahnya, tapi apakah *field* yang dibutuhkan terbaca benar:
nama item, jumlah, harga, subtotal, biaya tambahan, dan total. Jadi evaluasi
dilakukan per field:

- Deteksi item   : precision / recall / F1 (item prediksi dipasangkan ke item
                   ground truth berdasarkan kemiripan nama).
- Nama item      : CER (Character Error Rate) rata-rata dari item yang terpasang.
- Angka item     : akurasi jumlah, harga satuan, dan total harga.
- Ringkasan nota : subtotal, total, dan biaya tambahan tepat atau tidak.
- Konsistensi    : apakah hasil model lolos cek hitungan (item = subtotal, dst.).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from modules.schema import Receipt
from modules.validation import TOLERANCE, check_receipt, has_errors, normalize_receipt

NAME_MATCH_THRESHOLD = 0.5


def normalize_text(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    return " ".join(text.split())


def levenshtein(a: str, b: str) -> int:
    """Jumlah minimum operasi (sisip, hapus, ganti) untuk mengubah a menjadi b."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b))
            )
        previous = current
    return previous[-1]


def cer(prediction: str, reference: str) -> float:
    reference, prediction = normalize_text(reference), normalize_text(prediction)
    if not reference:
        return 0.0 if not prediction else 1.0
    return levenshtein(prediction, reference) / len(reference)


def match_items(pred: Receipt, gt: Receipt) -> list[tuple[int, int]]:
    """Pasangkan item prediksi ke item ground truth (greedy, kemiripan nama tertinggi dulu)."""
    candidates = []
    for p_idx, p_item in enumerate(pred.items):
        for g_idx, g_item in enumerate(gt.items):
            score = SequenceMatcher(None, normalize_text(p_item.name), normalize_text(g_item.name)).ratio()
            # bonus kecil kalau harganya sama, membantu nama yang mirip-mirip
            if abs(p_item.total_price - g_item.total_price) <= TOLERANCE:
                score += 0.2
            if score >= NAME_MATCH_THRESHOLD:
                candidates.append((score, p_idx, g_idx))

    pairs, used_p, used_g = [], set(), set()
    for _, p_idx, g_idx in sorted(candidates, reverse=True):
        if p_idx not in used_p and g_idx not in used_g:
            pairs.append((p_idx, g_idx))
            used_p.add(p_idx)
            used_g.add(g_idx)
    return pairs


def _same(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= TOLERANCE


def evaluate_receipt(pred: Receipt | None, gt: Receipt) -> dict:
    """Hitung semua metrik untuk satu nota. `pred=None` berarti model gagal total.

    `pred` sebaiknya hasil murni model (sebelum normalisasi) supaya subtotal/total
    yang tidak terbaca tidak "tertolong" oleh pengisian otomatis.
    """
    n_gt = len(gt.items)
    if pred is None:
        return {
            "parsed": False, "n_gt_items": n_gt, "n_pred_items": 0, "item_precision": 0.0,
            "item_recall": 0.0, "item_f1": 0.0, "name_cer": 1.0, "qty_acc": 0.0,
            "unit_price_acc": 0.0, "total_price_acc": 0.0, "item_exact_rate": 0.0,
            "subtotal_ok": False, "charges_recall": 0.0, "total_ok": False, "consistent": False,
        }

    pairs = match_items(pred, gt)
    n_pred, n_match = len(pred.items), len(pairs)
    precision = n_match / n_pred if n_pred else 0.0
    recall = n_match / n_gt if n_gt else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    qty_ok = price_ok = unit_ok = exact = 0
    cers = []
    for p_idx, g_idx in pairs:
        p, g = pred.items[p_idx], gt.items[g_idx]
        cers.append(cer(p.name, g.name))
        qty_ok += abs(p.quantity - g.quantity) < 1e-6
        unit_ok += _same(p.unit_price, g.unit_price)
        price_ok += _same(p.total_price, g.total_price)
        exact += cer(p.name, g.name) <= 0.1 and abs(p.quantity - g.quantity) < 1e-6 and _same(
            p.total_price, g.total_price
        )

    gt_charges = [c.amount for c in gt.charges]
    pred_charges = [c.amount for c in pred.charges]
    found = 0
    for amount in gt_charges:
        match = next((x for x in pred_charges if abs(x - amount) <= TOLERANCE), None)
        if match is not None:
            found += 1
            pred_charges.remove(match)

    return {
        "parsed": True,
        "n_gt_items": n_gt,
        "n_pred_items": n_pred,
        "item_precision": precision,
        "item_recall": recall,
        "item_f1": f1,
        "name_cer": sum(cers) / len(cers) if cers else 1.0,
        # akurasi angka dihitung terhadap jumlah item ground truth,
        # jadi item yang tidak terdeteksi juga dihitung salah
        "qty_acc": qty_ok / n_gt if n_gt else 0.0,
        "unit_price_acc": unit_ok / n_gt if n_gt else 0.0,
        "total_price_acc": price_ok / n_gt if n_gt else 0.0,
        "item_exact_rate": exact / n_gt if n_gt else 0.0,
        "subtotal_ok": _same(pred.subtotal, gt.subtotal),
        "charges_recall": found / len(gt_charges) if gt_charges else 1.0,
        "total_ok": _same(pred.total, gt.total),
        # konsistensi dicek setelah normalisasi, sama seperti yang dilihat user di aplikasi
        "consistent": not has_errors(check_receipt(normalize_receipt(pred))),
    }
