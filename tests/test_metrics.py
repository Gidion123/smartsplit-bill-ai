from modules.schema import ExtraCharge, Receipt, ReceiptItem
from research.metrics import cer, evaluate_receipt

GT = Receipt(
    items=[
        ReceiptItem(name="Nasi Goreng Spesial", quantity=1, unit_price=30000, total_price=30000),
        ReceiptItem(name="Es Jeruk", quantity=2, unit_price=8000, total_price=16000),
    ],
    subtotal=46000,
    charges=[ExtraCharge(name="PB1", amount=4600)],
    total=50600,
)


def test_cer():
    assert cer("nasi goreng", "nasi goreng") == 0
    assert cer("nasi gorng", "nasi goreng") == 1 / 11


def test_perfect_prediction():
    m = evaluate_receipt(GT, GT)
    assert m["item_f1"] == 1 and m["total_ok"] and m["charges_recall"] == 1 and m["consistent"]


def test_missing_item_and_wrong_total():
    pred = GT.model_copy(deep=True)
    pred.items = pred.items[:1]
    pred.total = 50000
    m = evaluate_receipt(pred, GT)
    assert m["item_recall"] == 0.5 and m["item_precision"] == 1
    assert not m["total_ok"]


def test_failed_prediction():
    assert evaluate_receipt(None, GT)["item_f1"] == 0
