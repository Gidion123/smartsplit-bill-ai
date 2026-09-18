"""Uji alur aplikasi end-to-end memakai Streamlit AppTest dengan reader palsu
(tanpa memanggil API DeepSeek)."""

from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from modules.readers.base import ReceiptReader
from modules.schema import ExtraCharge, Receipt, ReceiptItem

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class FakeReader(ReceiptReader):
    label = "Fake"

    def _predict(self, image):
        receipt = Receipt(
            merchant_name="Warung Test",
            items=[
                ReceiptItem(name="Nasi Goreng", quantity=2, unit_price=25000, total_price=50000),
                ReceiptItem(name="Es Teh", quantity=3, unit_price=5000, total_price=15000),
            ],
            subtotal=65000,
            charges=[ExtraCharge(name="PB1 10%", amount=6500)],
            total=71500,
        )
        return receipt, "{}"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-untuk-test")
    monkeypatch.setattr("modules.readers.create_reader", lambda key, **kw: FakeReader())
    monkeypatch.setattr("modules.ui.step_upload.create_reader", lambda key, **kw: FakeReader())
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    return at


def click(at, label):
    [b for b in at.button if b.label == label][0].click()
    at.run()


def test_full_flow(app):
    at = app
    assert not at.exception

    # langkah 1: gambar diisi langsung ke session supaya tidak perlu file uploader
    at.session_state.image = Image.new("RGB", (400, 800), "white")
    at.run()
    click(at, "Baca nota dengan AI")
    assert at.session_state.step == 1

    # langkah 2: data hasil bacaan sudah konsisten, tidak ada error
    assert not at.error
    click(at, "Lanjut →")
    assert at.session_state.step == 2

    # langkah 3: tambah peserta lalu bagi semua item
    at.text_input(key="participant_name_input").input("Andi, Budi, Citra").run()
    at.button(key="FormSubmitter:add_participants-Tambah").click().run()
    assert at.session_state.participants == ["Andi", "Budi", "Citra"]

    at.multiselect[0].set_value(["Andi", "Budi"]).run()
    click(at, "Item yang belum dipilih → bagi rata ke semua")
    click(at, "Hitung tagihan →")

    # langkah 4: total semua orang harus sama dengan total bill
    assert at.session_state.step == 3
    assert not at.exception
    assert any("sama persis" in s.value for s in at.success)
