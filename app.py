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

st.title("🏍️ オートレースAI Mobile v1.2")

url = st.text_input(
    "WINTICKET URL",
    value="https://www.winticket.jp/autorace/isesaki/racecard/2026062403/1/12"
)

def is_valid_name(name):
    if not name:
        return False
    if len(name) < 2 or len(name) > 5:
        return False
    ng = ["ナイター", "締切", "m", "試走", "投票", "オッズ", "人気", "良走路"]
    if name in ng:
        return False
    return bool(re.fullmatch(r"[一-龥ぁ-んァ-ヶ々]+", name))

def extract_players(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    candidates = re.findall(r"([1-8])\s+([一-龥ぁ-んァ-ヶ々]{2,5})", text)

    rows = []
    seen_cars = set()

    for car, name in candidates:
        if car in seen_cars:
            continue
        if is_valid_name(name):
            rows.append([int(car), name])
            seen_cars.add(car)

    rows = sorted(rows, key=lambda x: x[0])
    return rows[:8]

if st.button("出走表取得"):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=20)

        st.success("ページ取得成功")

        players = extract_players(r.text)

        if players:
            df = pd.DataFrame(players, columns=["車番", "選手名"])
            st.subheader("出走表")
            st.dataframe(df, use_container_width=True)
            st.info(f"取得人数: {len(df)}人")
        else:
            st.warning("選手取得失敗。次でHTML構造からさらに強化します。")

    except Exception as e:
        st.error(str(e))
