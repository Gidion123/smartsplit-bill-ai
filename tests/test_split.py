import pytest

from modules.schema import ExtraCharge, Receipt, ReceiptItem
from modules.split import SplitError, allocate_rounding, split_bill


@pytest.fixture
def receipt():
    return Receipt(
        items=[
            ReceiptItem(name="Chicken Rice", quantity=1, unit_price=55000, total_price=55000),
            ReceiptItem(name="Red Velvet", quantity=1, unit_price=38000, total_price=38000),
            ReceiptItem(name="Kentang", quantity=1, unit_price=33333, total_price=33333),
        ],
        subtotal=126333,
        charges=[
            ExtraCharge(name="Service 5%", amount=6317),
            ExtraCharge(name="PB1 10%", amount=13265),
            ExtraCharge(name="Diskon", amount=-10000),
        ],
        total=135915,
    )


def test_total_per_person_equals_bill_total(receipt):
    assignment = {0: {"Adi": 1}, 1: {"Ana": 1}, 2: {"Adi": 1, "Ana": 1, "Lala": 1}}
    result = split_bill(receipt, ["Adi", "Ana", "Lala"], assignment)
    assert result.people_total == receipt.total
    assert result.is_balanced
    assert all(p.total == int(p.total) for p in result.people)  # IDR tanpa desimal


def test_charges_are_proportional_to_subtotal(receipt):
    assignment = {0: {"Adi": 1}, 1: {"Ana": 1}, 2: {"Adi": 1}}
    result = split_bill(receipt, ["Adi", "Ana"], assignment)
    adi, ana = result.people
    ratio = adi.subtotal / receipt.subtotal
    assert adi.charges_sum == pytest.approx(receipt.charges_sum * ratio)
    assert adi.total + ana.total == receipt.total


def test_custom_portion(receipt):
    assignment = {0: {"Adi": 2, "Ana": 1}, 1: {"Ana": 1}, 2: {"Ana": 1}}
    result = split_bill(receipt, ["Adi", "Ana"], assignment)
    assert result.people[0].items[0].amount == pytest.approx(55000 * 2 / 3)


def test_participant_without_item_pays_zero(receipt):
    assignment = {0: {"Adi": 1}, 1: {"Adi": 1}, 2: {"Adi": 1}}
    result = split_bill(receipt, ["Adi", "Budi"], assignment)
    assert result.people[1].total == 0
    assert result.people[0].total == receipt.total


def test_unassigned_item_raises(receipt):
    with pytest.raises(SplitError):
        split_bill(receipt, ["Adi"], {0: {"Adi": 1}})


def test_allocate_rounding_keeps_sum():
    assert sum(allocate_rounding([100 / 3] * 3, 100)) == 100
    values = allocate_rounding([10.005, 20.004, 30.001], 60.01, decimals=2)
    assert round(sum(values), 2) == 60.01
