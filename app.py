import re
import requests
import numpy as np
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="オートレースAI Mobile v3.0", layout="wide")

st.title("🏍️ オートレースAI Mobile v3.0")
st.caption("買い目生成ロジック一新・指定点数完全一致版")

DEFAULT_URL = "https://www.winticket.jp/autorace/isesaki/racecard/2026062403/1/12"
url = st.text_input("WINTICKET 出走表URL", DEFAULT_URL)

st.sidebar.header("買い目点数")
auto_points = st.sidebar.checkbox("荒れ度AIで点数を自動調整", value=False)

max_2_honsen = st.sidebar.slider("2連単 🔥本線", 1, 10, 3)
max_2_ana = st.sidebar.slider("2連単 🎯穴", 1, 10, 3)
max_2_osae = st.sidebar.slider("2連単 🛡️抑え", 1, 10, 3)

max_3_honsen = st.sidebar.slider("3連単 🔥本線", 1, 15, 5)
max_3_ana = st.sidebar.slider("3連単 🎯穴", 1, 15, 3)
max_3_osae = st.sidebar.slider("3連単 🛡️抑え", 1, 25, 10)

st.sidebar.header("シミュレーション")
sim_count = st.sidebar.slider("シミュレーション回数", 300, 5000, 1000, step=100)
sim_strength = st.sidebar.slider("AI指数の強さ", 0.5, 3.0, 1.4, step=0.1)

st.sidebar.header("オッズ・期待値")
use_odds = st.sidebar.checkbox("オッズ取得を使う", value=True)
max_value_bets = st.sidebar.slider("期待値AI 表示点数", 3, 20, 8)
max_odds_filter = st.sidebar.slider("期待値AI 最大オッズ", 30.0, 500.0, 120.0)
min_ai_bet_score = st.sidebar.slider("期待値AI 最低AI買い目指数", 50.0, 100.0, 75.0)


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def racecard_to_odds_url(url):
    return url.replace("/racecard/", "/odds/")


def extract_race_info(text):
    info = {}

    m = re.search(r"(\d+)\s*R", text)
    if m:
        info["レース"] = f"{m.group(1)}R"

    m = re.search(r"(SG|GⅠ|GⅡ|GⅢ|G1|G2|G3|一般|特別|優勝戦|予選|準決勝)", text)
    if m:
        info["グレード"] = m.group(1)

    m = re.search(r"発走\s*(\d{1,2}:\d{2})", text)
    if m:
        info["発走"] = m.group(1)

    m = re.search(r"(晴|曇|雨|小雨|雪|小雪)\s+気温", text)
    if m:
        info["天候"] = m.group(1)
    else:
        for w in ["小雨", "雨", "晴", "曇", "小雪", "雪"]:
            if w in text:
                info["天候"] = w
                break

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


def parse_players(text):
    rows = []
    text = clean_text(text)

    marker = "車 選手名 ハンデ ST 試走T"
    if marker in text:
        text = text.split(marker, 1)[1]

    starts = list(re.finditer(r"(?:^| )([1-8])\s+([^\d\s]+)\s+\d+\s*期", text))

    for i, match in enumerate(starts):
        block = text[match.start(): starts[i + 1].start() if i + 1 < len(starts) else len(text)].strip()
        car_no = match.group(1)

        base = re.search(r"([1-8])\s+(.+?)\s+(\d+)\s*期\s+(\d+)\s*歳\s+(\S+)\s+", block)
        if not base:
            continue

        main = re.search(
            r"(\d+)\s*m\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
            r"([ASB]-?\d+|S-\d+)\s*\(\s*([ASB]-?\d+|S-\d+)\s*\)",
            block,
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

        rows.append({
            "車番": int(car_no),
            "選手名": base.group(2).strip(),
            "期": base.group(3),
            "年齢": int(base.group(4)),
            "所属": base.group(5),
            "ハンデ": handicap,
            "ハンデ数値": handicap_num,
            "ST": st_time,
            "試走T": trial_time,
            "偏差": deviation,
            "審査P": judge_p,
            "現ランク": current_rank,
            "前ランク": previous_rank,
            "2連対率": rates[0] if len(rates) > 0 else "",
            "3連対率": rates[1] if len(rates) > 1 else "",
            "良2連対率": rates[2] if len(rates) > 2 else "",
            "良3連対率": rates[3] if len(rates) > 3 else "",
            "湿2連対率": rates[4] if len(rates) > 4 else "",
            "湿3連対率": rates[5] if len(rates) > 5 else "",
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("車番").reset_index(drop=True)

    return df


def to_numeric_safe(df):
    cols = [
        "ハンデ数値", "ST", "試走T", "偏差", "審査P",
        "2連対率", "3連対率", "良2連対率", "良3連対率",
        "湿2連対率", "湿3連対率",
    ]
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def minmax_score(series, reverse=False):
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


def handicap_score(h):
    if h >= 20:
        return 100
    if h >= 10:
        return 65
    return 40


def rank_bonus(rank):
    if not isinstance(rank, str):
        return 0

    if rank.startswith("S-"):
        m = re.search(r"S-(\d+)", rank)
        if m:
            n = int(m.group(1))
            if n == 1:
                return 20
            if n <= 10:
                return 15
            return 12
        return 12

    m = re.search(r"A-(\d+)", rank)
    if m:
        n = int(m.group(1))
        if n <= 30:
            return 9
        if n <= 60:
            return 7
        if n <= 100:
            return 5
        if n <= 150:
            return 3
        return 1

    return 0


def add_trial_rank_bonus(df):
    df = df.copy()
    df["試走順位"] = df["試走T"].rank(method="min", ascending=True)
    df["試走順位補正"] = df["試走順位"].map(lambda r: 10 if r == 1 else 5 if r == 2 else 2 if r == 3 else 0)
    return df


def add_same_handicap_bonus(df):
    df = df.copy()
    df["同ハンデ試走順位"] = 0
    df["同ハンデST順位"] = 0
    df["同ハンデ補正"] = 0.0

    for h in sorted(df["ハンデ数値"].dropna().unique()):
        idx = df[df["ハンデ数値"] == h].index
        if len(idx) <= 1:
            df.loc[idx, "同ハンデ試走順位"] = 1
            df.loc[idx, "同ハンデST順位"] = 1
        else:
            df.loc[idx, "同ハンデ試走順位"] = df.loc[idx, "試走T"].rank(method="min", ascending=True)
            df.loc[idx, "同ハンデST順位"] = df.loc[idx, "ST"].rank(method="min", ascending=True)

    def bonus(row):
        b = 0
        h = row["ハンデ数値"]
        tr = row["同ハンデ試走順位"]
        sr = row["同ハンデST順位"]

        if h == 0:
            if tr == 1:
                b += 15
            if sr == 1:
                b += 10
        elif h == 10:
            if tr == 1:
                b += 8
            if sr == 1:
                b += 5
        else:
            if tr == 1:
                b += 3
        return b

    df["同ハンデ補正"] = df.apply(bonus, axis=1)
    return df


def add_track_condition_index(df, race_info):
    df = df.copy()
    df["良走路指数"] = df["良2連対率"].fillna(0) * 0.4 + df["良3連対率"].fillna(0) * 0.6
    df["湿走路指数"] = df["湿2連対率"].fillna(0) * 0.4 + df["湿3連対率"].fillna(0) * 0.6

    road = race_info.get("走路", "")

    if road == "良走路":
        df["走路補正"] = df["良走路指数"] * 0.08
    elif road == "湿走路":
        df["走路補正"] = df["湿走路指数"] * 0.12
    elif road == "斑走路":
        df["走路補正"] = df["良走路指数"] * 0.05 + df["湿走路指数"] * 0.08
    else:
        df["走路補正"] = 0

    return df


def add_weather_bonus(df, race_info):
    df = df.copy()
    weather = race_info.get("天候", "")
    road = race_info.get("走路", "")
    df["天候補正"] = 0.0

    if weather in ["雨", "小雨"] or road == "湿走路":
        df["天候補正"] += df["湿3連対率"].fillna(0) * 0.10
        df["天候補正"] += df["湿2連対率"].fillna(0) * 0.05
    elif weather == "晴" and road == "良走路":
        df["天候補正"] += df["良3連対率"].fillna(0) * 0.04
        df["天候補正"] += df["良2連対率"].fillna(0) * 0.03
    elif weather == "曇" and road == "良走路":
        df["天候補正"] += df["良3連対率"].fillna(0) * 0.03
        df["天候補正"] += df["良2連対率"].fillna(0) * 0.02

    return df


def add_himo_index(df, race_info):
    df = df.copy()
    road = race_info.get("走路", "")

    base_himo = (
        df["3連対率"].fillna(0) * 0.35 +
        df["良3連対率"].fillna(0) * 0.25 +
        df["湿3連対率"].fillna(0) * 0.25 +
        df["2連対率"].fillna(0) * 0.10 +
        df["良2連対率"].fillna(0) * 0.05
    )

    if road == "良走路":
        road_himo = df["良3連対率"].fillna(0) * 0.20
    elif road == "湿走路":
        road_himo = df["湿3連対率"].fillna(0) * 0.30
    elif road == "斑走路":
        road_himo = df["良3連対率"].fillna(0) * 0.10 + df["湿3連対率"].fillna(0) * 0.20
    else:
        road_himo = 0

    trial_himo = minmax_score(df["試走T"], reverse=True) * 0.08
    st_himo = minmax_score(df["ST"], reverse=True) * 0.04

    def front_bonus(h):
        if pd.isna(h):
            return 0
        if h == 0:
            return 20
        if h == 10:
            return 10
        return 0

    def keep_bonus(row):
        b = 0
        h = row.get("ハンデ数値", None)
        stv = row.get("ST", None)

        if pd.notna(h) and h == 0:
            b += 10
        if pd.notna(stv) and stv <= 0.18:
            b += 5
        if pd.notna(h) and h == 10 and pd.notna(stv) and stv <= 0.15:
            b += 3
        return b

    df["前残り補正"] = df["ハンデ数値"].apply(front_bonus) + df.apply(keep_bonus, axis=1)

    df["3着ヒモ指数"] = (
        base_himo +
        road_himo +
        trial_himo +
        st_himo +
        df["前残り補正"] +
        df["同ハンデ補正"] +
        df["天候補正"]
    )

    df["3着ヒモ指数"] = df["3着ヒモ指数"].round(2)
    df["ヒモ順位"] = df["3着ヒモ指数"].rank(method="min", ascending=False).astype(int)

    return df


def add_ai_index(df, race_info):
    if df.empty:
        return df

    df = df.copy()
    df["審査P補正"] = df["審査P"].clip(upper=100)

    df["審査Pスコア"] = minmax_score(df["審査P補正"])
    df["試走Tスコア"] = minmax_score(df["試走T"], reverse=True)
    df["STスコア"] = minmax_score(df["ST"], reverse=True)
    df["2連対スコア"] = minmax_score(df["2連対率"])
    df["3連対スコア"] = minmax_score(df["3連対率"])
    df["ハンデスコア"] = df["ハンデ数値"].apply(handicap_score)
    df["ランク補正"] = df["現ランク"].apply(rank_bonus)

    df = add_trial_rank_bonus(df)
    df = add_same_handicap_bonus(df)
    df = add_track_condition_index(df, race_info)
    df = add_weather_bonus(df, race_info)

    df["基礎AI指数"] = (
        df["審査Pスコア"] * 0.25 +
        df["試走Tスコア"] * 0.30 +
        df["STスコア"] * 0.15 +
        df["2連対スコア"] * 0.12 +
        df["3連対スコア"] * 0.08 +
        df["ハンデスコア"] * 0.05 +
        df["ランク補正"] * 0.05
    )

    df["AI指数"] = (
        df["基礎AI指数"] +
        df["走路補正"] +
        df["試走順位補正"] +
        df["天候補正"] * 0.20
    )

    df = add_himo_index(df, race_info)

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].round(2)

    df = df.sort_values("AI指数", ascending=False).reset_index(drop=True)

    marks = ["◎", "○", "▲", "△", "☆", "注", "抑", "紐"]
    df["印"] = [marks[i] if i < len(marks) else "紐" for i in range(len(df))]

    return df


def softmax(values, strength=1.0):
    arr = np.array(values, dtype=float)
    arr = arr - np.nanmax(arr)
    exp = np.exp(arr * strength / 20)
    s = exp.sum()
    if s <= 0:
        return np.ones(len(arr)) / len(arr)
    return exp / s


def add_simulation(df, n_sim=1000, strength=1.4):
    if df.empty:
        return df

    df = df.copy()
    cars = df["車番"].astype(int).tolist()

    ai = df["AI指数"].fillna(0).astype(float).tolist()
    himo = df["3着ヒモ指数"].fillna(0).astype(float).tolist()

    first_count = {c: 0 for c in cars}
    second_count = {c: 0 for c in cars}
    third_count = {c: 0 for c in cars}

    for _ in range(n_sim):
        remaining = cars.copy()

        p1 = softmax([ai[cars.index(c)] for c in remaining], strength)
        first = int(np.random.choice(remaining, p=p1))
        remaining.remove(first)

        p2_base = []
        for c in remaining:
            idx = cars.index(c)
            p2_base.append(ai[idx] * 0.75 + himo[idx] * 0.25)
        p2 = softmax(p2_base, strength * 0.9)
        second = int(np.random.choice(remaining, p=p2))
        remaining.remove(second)

        p3_base = []
        for c in remaining:
            idx = cars.index(c)
            p3_base.append(himo[idx] * 0.65 + ai[idx] * 0.35)
        p3 = softmax(p3_base, strength * 0.8)
        third = int(np.random.choice(remaining, p=p3))

        first_count[first] += 1
        second_count[second] += 1
        third_count[third] += 1

    df["1着率"] = df["車番"].map(lambda c: round(first_count[int(c)] / n_sim * 100, 1))
    df["2着率"] = df["車番"].map(lambda c: round(second_count[int(c)] / n_sim * 100, 1))
    df["3着率"] = df["車番"].map(lambda c: round(third_count[int(c)] / n_sim * 100, 1))
    df["連対率Sim"] = (df["1着率"] + df["2着率"]).round(1)
    df["3連対率Sim"] = (df["1着率"] + df["2着率"] + df["3着率"]).round(1)

    return df


def calc_confidence(df):
    if df.empty or len(df) < 2:
        return {"label": "判定不可", "stars": "☆☆☆☆☆", "comment": "データ不足", "gap": 0}

    gap = float(df.iloc[0]["AI指数"]) - float(df.iloc[1]["AI指数"])

    if gap >= 45:
        return {"label": "超本命寄り", "stars": "★★★★★", "comment": "1位の指数が大きく抜けています。ただし3着ヒモ荒れ注意。", "gap": round(gap, 2)}
    if gap >= 30:
        return {"label": "本命寄り", "stars": "★★★★☆", "comment": "1位優勢。3着はヒモ指数・前残り・天候を重視。", "gap": round(gap, 2)}
    if gap >= 15:
        return {"label": "やや本命", "stars": "★★★☆☆", "comment": "上位拮抗気味。穴も注意。", "gap": round(gap, 2)}
    if gap >= 8:
        return {"label": "混戦", "stars": "★★☆☆☆", "comment": "指数差が小さめ。穴・抑えも必要。", "gap": round(gap, 2)}
    return {"label": "大混戦", "stars": "★☆☆☆☆", "comment": "指数差がかなり小さいです。荒れ注意。", "gap": round(gap, 2)}


def calc_roughness(df, race_info):
    if df.empty or len(df) < 3:
        return {"label": "判定不可", "stars": "☆☆☆☆☆", "score": 0, "comment": "データ不足"}

    gap1 = float(df.iloc[0]["AI指数"]) - float(df.iloc[1]["AI指数"])
    gap2 = float(df.iloc[1]["AI指数"]) - float(df.iloc[2]["AI指数"])
    road = race_info.get("走路", "")
    weather = race_info.get("天候", "")
    humidity = float(race_info.get("湿度", 0) or 0)

    trial_values = df["試走T"].dropna()
    trial_gap = float(trial_values.max() - trial_values.min()) if len(trial_values) else 0

    score = 0

    if gap1 < 8:
        score += 35
    elif gap1 < 15:
        score += 25
    elif gap1 < 30:
        score += 15
    elif gap1 < 45:
        score += 8
    else:
        score += 2

    if gap2 < 5:
        score += 10

    if road == "湿走路":
        score += 30
    elif road == "斑走路":
        score += 25
    elif road == "風走路":
        score += 18
    elif road == "良走路":
        score += 5

    if weather in ["雨", "小雨"]:
        score += 20
    elif weather == "曇":
        score += 5

    if humidity >= 80:
        score += 10
    elif humidity >= 65:
        score += 5

    if trial_gap <= 0.03:
        score += 15
    elif trial_gap <= 0.05:
        score += 10
    elif trial_gap <= 0.07:
        score += 5

    ai_top4 = set(df.head(4)["車番"].astype(int).tolist())
    himo_top4 = set(df.sort_values("3着ヒモ指数", ascending=False).head(4)["車番"].astype(int).tolist())
    score += len(himo_top4 - ai_top4) * 6

    score = min(score, 100)

    if score >= 80:
        label, stars, comment = "超荒れ", "★★★★★", "荒れ要素がかなり強いです。穴・抑え厚め。"
    elif score >= 60:
        label, stars, comment = "荒れ", "★★★★☆", "荒れやすい条件です。ヒモ抜け注意。"
    elif score >= 40:
        label, stars, comment = "普通", "★★★☆☆", "本線も穴もバランス型。"
    elif score >= 20:
        label, stars, comment = "堅め", "★★☆☆☆", "上位中心でよさそうです。"
    else:
        label, stars, comment = "超本命", "★☆☆☆☆", "かなり本命寄りです。点数絞り向き。"

    return {
        "label": label,
        "stars": stars,
        "score": round(score, 1),
        "comment": comment,
        "gap1": round(gap1, 2),
        "trial_gap": round(trial_gap, 3),
    }


def adjust_points_by_roughness(roughness, manual, auto):
    if not auto:
        return manual

    score = roughness.get("score", 0)
    p = manual.copy()

    if score >= 80:
        p["2_honsen"] = max(2, manual["2_honsen"] - 1)
        p["2_ana"] = min(10, manual["2_ana"] + 3)
        p["2_osae"] = min(10, manual["2_osae"] + 3)
        p["3_honsen"] = max(3, manual["3_honsen"] - 1)
        p["3_ana"] = min(15, manual["3_ana"] + 5)
        p["3_osae"] = min(25, manual["3_osae"] + 8)
    elif score >= 60:
        p["2_ana"] = min(10, manual["2_ana"] + 2)
        p["2_osae"] = min(10, manual["2_osae"] + 2)
        p["3_ana"] = min(15, manual["3_ana"] + 3)
        p["3_osae"] = min(25, manual["3_osae"] + 5)
    elif score >= 40:
        pass
    elif score >= 20:
        p["2_ana"] = max(1, manual["2_ana"] - 1)
        p["2_osae"] = max(1, manual["2_osae"] - 1)
        p["3_honsen"] = max(3, manual["3_honsen"] - 1)
        p["3_ana"] = max(1, manual["3_ana"] - 1)
        p["3_osae"] = max(2, manual["3_osae"] - 3)
    else:
        p["2_honsen"] = min(manual["2_honsen"], 2)
        p["2_ana"] = min(manual["2_ana"], 1)
        p["2_osae"] = min(manual["2_osae"], 1)
        p["3_honsen"] = min(manual["3_honsen"], 3)
        p["3_ana"] = min(manual["3_ana"], 1)
        p["3_osae"] = min(manual["3_osae"], 2)

    return p


def parse_odds_from_html(html, bet_type):
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    text = clean_text(text)
    rows = []

    if bet_type == "2連単":
        pattern = re.findall(r"([1-8])\s*-\s*([1-8])\s+(\d+(?:\.\d+)?)", text)
        for a, b, odd in pattern:
            if a != b:
                rows.append({"買い目": f"{a}-{b}", "オッズ": float(odd), "式別": "2連単"})

    elif bet_type == "3連単":
        pattern = re.findall(r"([1-8])\s*-\s*([1-8])\s*-\s*([1-8])\s+(\d+(?:\.\d+)?)", text)
        for a, b, c, odd in pattern:
            if len({a, b, c}) == 3:
                rows.append({"買い目": f"{a}-{b}-{c}", "オッズ": float(odd), "式別": "3連単"})

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    return df.sort_values("オッズ").drop_duplicates("買い目", keep="first").reset_index(drop=True)


def score_bet(bet, df):
    ai_map = {int(r["車番"]): float(r["AI指数"]) for _, r in df.iterrows()}
    himo_map = {int(r["車番"]): float(r["3着ヒモ指数"]) for _, r in df.iterrows()}
    sim1_map = {int(r["車番"]): float(r["1着率"]) for _, r in df.iterrows()}
    sim2_map = {int(r["車番"]): float(r["2着率"]) for _, r in df.iterrows()}
    sim3_map = {int(r["車番"]): float(r["3着率"]) for _, r in df.iterrows()}

    nums = [int(x) for x in bet.split("-")]

    if len(nums) == 2:
        a, b = nums
        return (
            ai_map.get(a, 0) * 0.35 +
            ai_map.get(b, 0) * 0.25 +
            sim1_map.get(a, 0) * 0.25 +
            sim2_map.get(b, 0) * 0.15
        )

    if len(nums) == 3:
        a, b, c = nums
        return (
            ai_map.get(a, 0) * 0.30 +
            ai_map.get(b, 0) * 0.20 +
            himo_map.get(c, 0) * 0.20 +
            sim1_map.get(a, 0) * 0.15 +
            sim2_map.get(b, 0) * 0.08 +
            sim3_map.get(c, 0) * 0.07
        )

    return 0


def adjusted_value_score(ai_score, odds):
    raw = ai_score * odds / 100
    if odds >= 80:
        return round(raw * 0.65, 2)
    if odds >= 50:
        return round(raw * 0.78, 2)
    if odds >= 30:
        return round(raw * 0.90, 2)
    return round(raw, 2)


def add_odds_to_bets(bets, odds_df, df, bet_type):
    odds_map = {}
    if odds_df is not None and not odds_df.empty:
        odds_map = dict(zip(odds_df["買い目"], odds_df["オッズ"]))

    rows = []
    for bet in bets:
        ai_score = score_bet(bet, df)
        odds = odds_map.get(bet, None)
        value = adjusted_value_score(ai_score, odds) if odds is not None else None
        rows.append({
            "式別": bet_type,
            "買い目": bet,
            "AI買い目指数": round(ai_score, 2),
            "オッズ": odds,
            "期待値指数": value,
        })

    return pd.DataFrame(rows)


def build_value_candidates(df, odds_df, bet_type, limit=8):
    if odds_df is None or odds_df.empty or df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in odds_df.iterrows():
        bet = row["買い目"]
        odds = float(row["オッズ"])

        if odds < 5.0 or odds > max_odds_filter:
            continue

        ai_score = score_bet(bet, df)
        if ai_score < min_ai_bet_score:
            continue

        rows.append({
            "式別": bet_type,
            "買い目": bet,
            "AI買い目指数": round(ai_score, 2),
            "オッズ": odds,
            "期待値指数": adjusted_value_score(ai_score, odds),
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    return out.sort_values(["期待値指数", "AI買い目指数"], ascending=False).head(limit).reset_index(drop=True)


def make_all_bets(df, bet_type):
    cars = df["車番"].astype(int).tolist()
    bets = []

    if bet_type == "2連単":
        for a in cars:
            for b in cars:
                if a != b:
                    bets.append(f"{a}-{b}")

    elif bet_type == "3連単":
        for a in cars:
            for b in cars:
                for c in cars:
                    if len({a, b, c}) == 3:
                        bets.append(f"{a}-{b}-{c}")

    return bets


def classify_bet(bet, df):
    nums = [int(x) for x in bet.split("-")]

    ai_rank = {
        int(row["車番"]): i + 1
        for i, (_, row) in enumerate(df.sort_values("AI指数", ascending=False).iterrows())
    }
    sim1_rank = {
        int(row["車番"]): i + 1
        for i, (_, row) in enumerate(df.sort_values("1着率", ascending=False).iterrows())
    }
    sim3_rank = {
        int(row["車番"]): i + 1
        for i, (_, row) in enumerate(df.sort_values("3着率", ascending=False).iterrows())
    }

    if len(nums) == 2:
        a, b = nums

        if sim1_rank.get(a, 99) <= 2 and ai_rank.get(b, 99) <= 4:
            return "本線"

        if sim1_rank.get(a, 99) <= 4 and a != df.iloc[0]["車番"]:
            return "穴"

        return "抑え"

    if len(nums) == 3:
        a, b, c = nums

        if sim1_rank.get(a, 99) <= 2 and ai_rank.get(b, 99) <= 4 and sim3_rank.get(c, 99) <= 5:
            return "本線"

        if sim1_rank.get(a, 99) in [2, 3, 4]:
            return "穴"

        return "抑え"

    return "抑え"


def generate_exact_bets(df, bet_type, honsen_n, ana_n, osae_n):
    all_bets = make_all_bets(df, bet_type)

    ranked = sorted(
        all_bets,
        key=lambda x: score_bet(x, df),
        reverse=True
    )

    buckets = {
        "本線": [],
        "穴": [],
        "抑え": [],
    }

    for bet in ranked:
        cat = classify_bet(bet, df)
        buckets[cat].append(bet)

    used = set()

    def pick(category, n):
        selected = []

        for bet in buckets[category]:
            if bet not in used:
                selected.append(bet)
                used.add(bet)
            if len(selected) == n:
                return selected

        for bet in ranked:
            if bet not in used:
                selected.append(bet)
                used.add(bet)
            if len(selected) == n:
                return selected

        return selected

    honsen = pick("本線", honsen_n)
    ana = pick("穴", ana_n)
    osae = pick("抑え", osae_n)

    honsen = honsen[:honsen_n]
    ana = ana[:ana_n]
    osae = osae[:osae_n]

    return honsen, ana, osae


if st.button("出走表を取得する", type="primary"):
    try:
        with st.spinner("WINTICKETから取得中..."):
            html = fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")
            text = clean_text(soup.get_text(" "))
            race_info = extract_race_info(text)

            df = parse_players(text)
            df = to_numeric_safe(df)
            df = add_ai_index(df, race_info)
            df = add_simulation(df, sim_count, sim_strength)

        odds_2_df = pd.DataFrame()
        odds_3_df = pd.DataFrame()

        if use_odds:
            try:
                with st.spinner("オッズ取得中..."):
                    odds_html = fetch_html(racecard_to_odds_url(url))
                    odds_2_df = parse_odds_from_html(odds_html, "2連単")
                    odds_3_df = parse_odds_from_html(odds_html, "3連単")
            except Exception as odds_error:
                st.warning(f"オッズ取得に失敗しました：{odds_error}")

        st.success(f"取得成功：{len(df)}車")

        if race_info:
            st.subheader("レース情報")
            st.json(race_info)

        if df.empty:
            st.error("選手データを取得できませんでした。")
            st.text_area("取得テキスト確認用", text[:5000], height=300)
        else:
            confidence = calc_confidence(df)
            roughness = calc_roughness(df, race_info)

            manual_points = {
                "2_honsen": max_2_honsen,
                "2_ana": max_2_ana,
                "2_osae": max_2_osae,
                "3_honsen": max_3_honsen,
                "3_ana": max_3_ana,
                "3_osae": max_3_osae,
            }

            points = adjust_points_by_roughness(roughness, manual_points, auto_points)

            col_conf, col_rough = st.columns(2)

            with col_conf:
                st.subheader("信頼度")
                st.markdown(f"### {confidence['stars']} {confidence['label']}")
                st.write(f"指数差：1位 - 2位 = **{confidence['gap']}**")
                st.write(confidence["comment"])

            with col_rough:
                st.subheader("荒れ度AI")
                st.markdown(f"### {roughness['stars']} {roughness['label']}")
                st.write(f"荒れ度スコア：**{roughness['score']} / 100**")
                st.write(f"試走差：**{roughness['trial_gap']}**")
                st.write(roughness["comment"])

            st.subheader("買い目点数")
            if auto_points:
                st.info(
                    f"自動調整ON：2連単 本線{points['2_honsen']} / 穴{points['2_ana']} / 抑え{points['2_osae']}、"
                    f"3連単 本線{points['3_honsen']} / 穴{points['3_ana']} / 抑え{points['3_osae']}"
                )
            else:
                st.info(
                    f"自動調整OFF：2連単 本線{points['2_honsen']} / 穴{points['2_ana']} / 抑え{points['2_osae']}、"
                    f"3連単 本線{points['3_honsen']} / 穴{points['3_ana']} / 抑え{points['3_osae']}"
                )

            st.subheader("AI指数ランキング")

            show_cols = [
                "印", "車番", "選手名", "ハンデ", "ST", "試走T",
                "1着率", "2着率", "3着率", "連対率Sim", "3連対率Sim",
                "3着ヒモ指数", "ヒモ順位",
                "前残り補正", "同ハンデ補正", "天候補正",
                "基礎AI指数", "AI指数",
            ]
            st.dataframe(df[show_cols], use_container_width=True)

            st.subheader("着順シミュレーションAI")
            sim_view = df.sort_values("1着率", ascending=False)
            st.dataframe(
                sim_view[
                    ["車番", "選手名", "1着率", "2着率", "3着率", "連対率Sim", "3連対率Sim", "AI指数", "3着ヒモ指数"]
                ],
                use_container_width=True
            )

            h2, a2, o2 = generate_exact_bets(
                df,
                "2連単",
                points["2_honsen"],
                points["2_ana"],
                points["2_osae"],
            )

            h3, a3, o3 = generate_exact_bets(
                df,
                "3連単",
                points["3_honsen"],
                points["3_ana"],
                points["3_osae"],
            )

            st.subheader("2連単予想")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"### 🔥 本線（{len(h2)}点）")
                st.dataframe(add_odds_to_bets(h2, odds_2_df, df, "2連単"), use_container_width=True)

            with col2:
                st.markdown(f"### 🎯 穴（{len(a2)}点）")
                st.dataframe(add_odds_to_bets(a2, odds_2_df, df, "2連単"), use_container_width=True)

            with col3:
                st.markdown(f"### 🛡️ 抑え（{len(o2)}点）")
                st.dataframe(add_odds_to_bets(o2, odds_2_df, df, "2連単"), use_container_width=True)

            st.subheader("3連単予想")
            col4, col5, col6 = st.columns(3)

            with col4:
                st.markdown(f"### 🔥 本線（{len(h3)}点）")
                st.dataframe(add_odds_to_bets(h3, odds_3_df, df, "3連単"), use_container_width=True)

            with col5:
                st.markdown(f"### 🎯 穴（{len(a3)}点）")
                st.dataframe(add_odds_to_bets(a3, odds_3_df, df, "3連単"), use_container_width=True)

            with col6:
                st.markdown(f"### 🛡️ 抑え（{len(o3)}点）")
                st.dataframe(add_odds_to_bets(o3, odds_3_df, df, "3連単"), use_container_width=True)

            if use_odds:
                st.subheader("期待値AI")
                col7, col8 = st.columns(2)

                with col7:
                    st.markdown("### 2連単 期待値")
                    value_2 = build_value_candidates(df, odds_2_df, "2連単", max_value_bets)
                    if value_2.empty:
                        st.info("2連単オッズを取得できないか、期待値候補がありません。")
                    else:
                        st.dataframe(value_2, use_container_width=True)

                with col8:
                    st.markdown("### 3連単 期待値")
                    value_3 = build_value_candidates(df, odds_3_df, "3連単", max_value_bets)
                    if value_3.empty:
                        st.info("3連単オッズを取得できないか、期待値候補がありません。")
                    else:
                        st.dataframe(value_3, use_container_width=True)

                with st.expander("取得オッズ確認"):
                    st.write("2連単オッズ取得件数:", len(odds_2_df))
                    if not odds_2_df.empty:
                        st.dataframe(odds_2_df.head(50), use_container_width=True)

                    st.write("3連単オッズ取得件数:", len(odds_3_df))
                    if not odds_3_df.empty:
                        st.dataframe(odds_3_df.head(50), use_container_width=True)

            st.subheader("3着ヒモ指数ランキング")
            himo_view = df.sort_values("3着ヒモ指数", ascending=False)
            st.dataframe(
                himo_view[
                    [
                        "車番", "選手名", "ハンデ", "ST", "試走T",
                        "3着率", "3着ヒモ指数", "ヒモ順位",
                        "前残り補正", "同ハンデ補正", "天候補正",
                        "AI指数", "印"
                    ]
                ],
                use_container_width=True
            )

            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "CSVダウンロード",
                data=csv,
                file_name="autorace_v3_0_exact_bets.csv",
                mime="text/csv",
            )

    except Exception as e:
        st.error("取得エラー")
        st.exception(e)
