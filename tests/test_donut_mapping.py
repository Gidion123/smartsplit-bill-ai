from modules.readers.donut_reader import cord_to_receipt


def test_cord_output_is_mapped_to_receipt():
    # contoh bentuk output token2json Donut CORD-v2
    cord = {
        "menu": [
            {"nm": "ICE BLACKCOFFEE", "cnt": "2", "price": "82,000"},
            {"nm": "AVOCADO COFFEE", "cnt": "1", "unitprice": "61,000", "price": "61,000"},
        ],
        "sub_total": {"subtotal_price": "143,000", "tax_price": "14,300", "discount_price": "5,000"},
        "total": {"total_price": "152,300", "cashprice": "200,000"},
    }
    receipt = cord_to_receipt(cord)
    assert [i.name for i in receipt.items] == ["ICE BLACKCOFFEE", "AVOCADO COFFEE"]
    assert receipt.items[0].quantity == 2
    assert receipt.subtotal == 143000
    assert {c.name: c.amount for c in receipt.charges} == {"Pajak": 14300, "Diskon": -5000}
    assert receipt.total == 152300


def test_single_menu_dict_is_supported():
    receipt = cord_to_receipt({"menu": {"nm": "Teh", "price": "5.000"}, "total": {"total_price": "5.000"}})
    assert len(receipt.items) == 1 and receipt.items[0].total_price == 5000
