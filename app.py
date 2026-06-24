import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(
    page_title="オートレースAI Mobile",
    page_icon="🏍️",
    layout="centered"
)

st.title("🏍️ オートレースAI Mobile v1.1")

url = st.text_input(
    "WINTICKET URL",
    value="https://www.winticket.jp/autorace/isesaki/racecard/2026062403/1/12"
)

def extract_players(html):

    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(" ", strip=True)

    players = []

    pattern = re.compile(
        r'(\d)\s+([^\d\s]{2,10})'
    )

    for m in pattern.finditer(text):

        car = m.group(1)
        name = m.group(2)

        if len(name) >= 2:
            players.append([car, name])

    unique = []

    seen = set()

    for car, name in players:

        key = f"{car}_{name}"

        if key not in seen:

            seen.add(key)

            unique.append([car, name])

    return unique[:8]

if st.button("出走表取得"):

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        st.success("ページ取得成功")

        players = extract_players(r.text)

        if len(players) > 0:

            df = pd.DataFrame(
                players,
                columns=["車番", "選手名"]
            )

            st.subheader("出走表")

            st.dataframe(
                df,
                use_container_width=True
            )

        else:

            st.warning(
                "選手取得失敗（次で解析強化）"
            )

    except Exception as e:

        st.error(str(e))
