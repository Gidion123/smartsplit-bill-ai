from modules.schema import ExtraCharge, Receipt, ReceiptItem
from modules.validation import check_receipt, coerce_receipt, has_errors, normalize_receipt, reconcile_receipt


def make_receipt(**overrides):
    data = dict(
        items=[
            ReceiptItem(name="Nasi Goreng", quantity=2, unit_price=25000, total_price=50000),
            ReceiptItem(name="Es Teh", quantity=1, unit_price=8000, total_price=8000),
        ],
        subtotal=58000,
        charges=[ExtraCharge(name="PB1 10%", amount=5800)],
        total=63800,
    )
    data.update(overrides)
    return Receipt(**data)


def test_consistent_receipt_has_no_issue():
    assert check_receipt(make_receipt()) == []


def test_wrong_total_is_error():
    issues = check_receipt(make_receipt(total=70000))
    assert has_errors(issues)


def test_reconcile_adds_gap_as_charge():
    fixed = reconcile_receipt(make_receipt(total=64000))
    assert fixed.charges[-1].amount == 200
    assert not has_errors(check_receipt(fixed))


def test_normalize_fills_missing_values_and_negative_discount():
    receipt = Receipt(
        items=[ReceiptItem(name="Kopi", quantity=2, total_price=30000)],
        charges=[ExtraCharge(name="Diskon member", amount=3000)],
    )
    result = normalize_receipt(receipt)
    assert result.items[0].unit_price == 15000
    assert result.subtotal == 30000
    assert result.charges[0].amount == -3000
    assert result.total == 27000


def test_coerce_receipt_from_text_values():
    data = {
        "items": [
            {"name": "Ayam Bakar", "quantity": "1", "unit_price": "35.000", "total_price": "35.000"},
            {"name": "", "total_price": "1.000"},  # tanpa nama -> dibuang
        ],
        "subtotal": "35.000",
        "charges": [{"name": "Service", "amount": "1,750"}],
        "total": "Rp36.750",
    }
    receipt = coerce_receipt(data)
    assert len(receipt.items) == 1
    assert receipt.items[0].total_price == 35000
    assert receipt.total == 36750
