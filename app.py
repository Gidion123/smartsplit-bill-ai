"""
SmartSplit Bill - aplikasi Streamlit untuk membaca nota dengan AI dan membagi tagihan.

Reader nota yang dipakai adalah DeepSeek (lihat notebooks/01_Research.ipynb
untuk perbandingan model dan alasan pemilihannya).

Jalankan:
    streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv

from modules.ui import step_assign, step_result, step_review, step_upload
from modules.ui.components import CUSTOM_CSS, render_header, render_stepper
from modules.ui.sidebar import render_sidebar
from modules.ui.state import init_state

# baca DEEPSEEK_API_KEY & DEEPSEEK_MODEL dari file .env (kalau ada)
load_dotenv()

st.set_page_config(page_title="SmartSplit Bill", page_icon="🧾", layout="wide")


def main() -> None:
    init_state()
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    settings = render_sidebar()

    render_header()
    render_stepper(st.session_state.step)
    st.markdown(" ")

    step = st.session_state.step
    if step == 0:
        step_upload.render(settings)
    elif step == 1:
        step_review.render(settings.currency)
    elif step == 2:
        step_assign.render(settings.currency)
    else:
        step_result.render(settings.currency)


main()
