import re
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="オートレースAI Mobile v1.5", layout="wide")

st.title("🏍️ オートレースAI Mobile v1.5")
st.caption("WINTICKET出走表取得 + AI指数表示")

DEFAULT_URL = "https://www.winticket.jp/autorace/isesaki/racecard/2026062403/1/12"

url = st.text_input("WINTICKET 出走表URL", DEFAULT_URL)


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }
    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()
    return res.text


def extract_race_info(text: str) -> dict:
    info = {}

    m = re.search(r"(\d+)\s*R", text)
    if m:
        info["レース"] = f"{m.group(1)}R"

    m = re.search(r"(GⅠ|GⅡ|GⅢ|SG|G1|G2|G3|G2|一般|特別|優勝戦|予選|準決勝)", text)
    if m:
        info["グレード"] = m.group(1)

    m = re.search(r"発走\s*(\d{1,2}:\d{2})", text)
    if m:
        info["発走"] = m.group(1)

    m = re.search(r"(良走路|湿走路|斑走路|風走路)\s*/\s*([\d.]+)\s*℃", text)
    if m:
        info["走路"] = m.group(1)
        info["走路温度"] = m.group(2)

    m = re.search(r"気温\s*([\d.]+)\s*℃", text)
    if m:
        info["気温"] = m.group(1)

    m = re.search(r"湿度\s*([\d.]+)\s*％", text)
    if m:
        info["湿度"] = m.group(1)

    return info


def parse_players(text: str) -> pd.DataFrame:
    rows = []
    text = clean_text(text)

    marker = "車 選手名 ハンデ ST 試走T"
    if marker in text:
        text = text.split(marker, 1)[1]

    starts = list(re.finditer(r"(?:^| )([1-8])\s+([^\d\s]+)\s+\d+\s*期", text))

    for i, match in enumerate(starts):
        start = match.start()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[start:end].strip()

        car_no = match.group(1)

        base = re.search(
            r"([1-8])\s+(.+?)\s+(\d+)\s*期\s+(\d+)\s*歳\s+(\S+)\s+",
            block
        )

        if not base:
            continue

        name = base.group(2).strip()
        term = base.group(3)
        age = base.group(4)
        home = base.group(5)

        main = re.search(
            r"(\d+)\s*m\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
            r"([ASB]-?\d+|S-\d+)\s*\(\s*([ASB]-?\d+|S-\d+)\s*\)",
            block
        )

        if main:
            handicap = f"{main.group(1)}m"
            handicap_num = int(main.group(1))
            st_time = main.group(2)
            trial_time = main.group(3)
            deviation = main.group(4)
            judge_p = main.group(5)
            current_rank = main.group(6)
            previous_rank = main.group(7)
        else:
            handicap = ""
            handicap_num = 0
            st_time = ""
            trial_time = ""
            deviation = ""
            judge_p = ""
            current_rank = ""
            previous_rank = ""

        rates = re.findall(r"(\d+(?:\.\d+)?)\s*%", block)

        rate_2 = rates[0] if len(rates) > 0 else ""
        rate_3 = rates[1] if len(rates) > 1 else ""
        good_2 = rates[2] if len(rates) > 2 else ""
        good_3 = rates[3] if len(rates) > 3 else ""
        wet_2 = rates[4] if len(rates) > 4 else ""
        wet_3 = rates[5] if len(rates) > 5 else ""

        rows.append({
            "車番": int(car_no),
            "選手名": name,
            "期": term,
            "年齢": int(age),
            "所属": home,
            "ハンデ": handicap,
            "ハンデ数値": handicap_num,
            "ST": st_time,
            "試走T": trial_time,
            "偏差": deviation,
            "審査P": judge_p,
            "現ランク": current_rank,
            "前ランク": previous_rank,
            "2連対率": rate_2,
            "3連対率": rate_3,
            "良2連対率": good_2,
            "良3連対率": good_3,
            "湿2連対率": wet_2,
            "湿3連対率": wet_3,
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values("車番").reset_index(drop=True)

    return df


def to_numeric_safe(df: pd.DataFrame) -> pd.DataFrame:
    num_cols = [
        "ハンデ数値",
        "ST",
        "試走T",
        "偏差",
        "審査P",
        "2連対率",
        "3連対率",
        "良2連対率",
        "良3連対率",
        "湿2連対率",
        "湿3連対率",
    ]

    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def minmax_score(series: pd.Series, reverse: bool = False) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")

    if s.isna().all():
        return pd.Series([50.0] * len(s), index=s.index)

    min_v = s.min()
    max_v = s.max()

    if max_v == min_v:
        return pd.Series([50.0] * len(s), index=s.index)

    if reverse:
        score = (max_v - s) / (max_v - min_v) * 100
    else:
        score = (s - min_v) / (max_v - min_v) * 100

    return score.fillna(50.0)


def handicap_score(handicap: float) -> float:
    if handicap >= 20:
        return 100
    elif handicap >= 10:
        return 65
    else:
        return 40


def rank_bonus(rank: str) -> float:
    if not isinstance(rank, str):
        return 0

    if rank.startswith("S-"):
        return 12

    m = re.search(r"A-(\d+)", rank)
    if m:
        num = int(m.group(1))
        if num <= 30:
            return 9
        elif num <= 60:
            return 7
        elif num <= 100:
            return 5
        elif num <= 150:
            return 3
        else:
            return 1

    return 0


def add_ai_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    df["審査Pスコア"] = minmax_score(df["審査P"])
    df["試走Tスコア"] = minmax_score(df["試走T"], reverse=True)
    df["STスコア"] = minmax_score(df["ST"], reverse=True)
    df["2連対スコア"] = minmax_score(df["2連対率"])
    df["3連対スコア"] = minmax_score(df["3連対率"])
    df["ハンデスコア"] = df["ハンデ数値"].apply(handicap_score)
    df["ランク補正"] = df["現ランク"].apply(rank_bonus)

    df["AI指数"] = (
        df["審査Pスコア"] * 0.35 +
        df["試走Tスコア"] * 0.25 +
        df["2連対スコア"] * 0.15 +
        df["3連対スコア"] * 0.10 +
        df["STスコア"] * 0.07 +
        df["ハンデスコア"] * 0.05 +
        df["ランク補正"] * 0.03
    )

    df["AI指数"] = df["AI指数"].round(2)

    df = df.sort_values("AI指数", ascending=False).reset_index(drop=True)

    marks = ["◎", "○", "▲", "△", "☆", "注", "抑", ""]
    df["印"] = [marks[i] if i < len(marks) else "" for i in range(len(df))]

    return df


if st.button("出走表を取得する", type="primary"):
    try:
        with st.spinner("WINTICKETから取得中..."):
            html = fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")
            text = clean_text(soup.get_text(" "))

            race_info = extract_race_info(text)
            df = parse_players(text)
            df = to_numeric_safe(df)
            df = add_ai_index(df)

        st.success(f"取得成功：{len(df)}車")

        if race_info:
            st.subheader("レース情報")
            st.json(race_info)

        st.subheader("AI指数ランキング")

        if df.empty:
            st.error("選手データを取得できませんでした。HTML構造が変わった可能性があります。")
            st.text_area("取得テキスト確認用", text[:5000], height=300)
        else:
            show_cols = [
                "印",
                "車番",
                "選手名",
                "ハンデ",
                "ST",
                "試走T",
                "審査P",
                "現ランク",
                "2連対率",
                "3連対率",
                "良2連対率",
                "良3連対率",
                "湿2連対率",
                "湿3連対率",
                "AI指数",
            ]

            st.dataframe(df[show_cols], use_container_width=True)

            st.subheader("指数詳細")
            detail_cols = [
                "車番",
                "選手名",
                "審査Pスコア",
                "試走Tスコア",
                "STスコア",
                "2連対スコア",
                "3連対スコア",
                "ハンデスコア",
                "ランク補正",
                "AI指数",
            ]
            st.dataframe(df[detail_cols], use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "CSVダウンロード",
                data=csv,
                file_name="autorace_v1_5_ai_index.csv",
                mime="text/csv",
            )

            st.subheader("確認ログ")
            st.write("取得列：", list(df.columns))
            st.write("AI指数順：")
            st.write(df[["印", "車番", "選手名", "AI指数"]])

    except Exception as e:
        st.error("取得エラー")
        st.exception(e)
