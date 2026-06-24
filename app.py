import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="オートレースAI Mobile",
    page_icon="🏍️",
    layout="centered"
)

st.title("🏍️ オートレースAI Mobile v1")

url = st.text_input(
    "WINTICKET URL",
    value="https://www.winticket.jp/autorace/isesaki/racecard/2026062403/1/12"
)

if st.button("出走表取得"):

    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(url, headers=headers, timeout=15)

        st.success("ページ取得成功")

        st.write("HTMLサイズ:", len(r.text))

    except Exception as e:
        st.error(e)
