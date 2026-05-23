"""Streamlit-дашборд с автообновлением в реальном времени."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"


def load_matches() -> pd.DataFrame:
    arrow = OUTPUT_DIR / "arrow_matches.parquet"
    if arrow.exists():
        return pd.read_parquet(arrow)

    rows = []
    for file in sorted(DATA_DIR.glob("matches_*.jsonl")):
        with file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    if rows:
        return pd.DataFrame(rows)

    clean = OUTPUT_DIR / "matches_clean.parquet"
    if clean.exists():
        return pd.read_parquet(clean)
    return pd.DataFrame()


def load_sliding_window() -> dict:
    path = OUTPUT_DIR / "nats_sliding_window.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_windows() -> pd.DataFrame:
    path = OUTPUT_DIR / "arrow_windows.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def main() -> None:
    st.set_page_config(page_title="Спортивная статистика", layout="wide")
    st.title("Лабораторная работа №14 — вариант 18")
    st.caption("Тарасов Вадим Романович, группа 221131")

    refresh_sec = st.sidebar.slider("Автообновление (сек)", 3, 30, 5)
    auto = st.sidebar.checkbox("Включить автообновление", value=True)
    if auto and st_autorefresh:
        st_autorefresh(interval=refresh_sec * 1000, key="sports_dashboard_refresh")
    elif auto:
        st.sidebar.info("Установите streamlit-autorefresh для автообновления")

    st.sidebar.write(f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}")

    df = load_matches()
    if df.empty:
        st.warning("Нет данных. Запустите run.ps1 или docker compose up")
        return

    sliding = load_sliding_window()
    if sliding:
        st.subheader("NATS: скользящее окно 5 минут")
        c1, c2, c3 = st.columns(3)
        c1.metric("Матчей в окне", sliding.get("matches", 0))
        c2.metric("Средние голы", round(sliding.get("avg_goals", 0), 2))
        c3.metric("Окно (мин)", sliding.get("window_minutes", 5))

    sports = sorted(df["sport"].dropna().unique())
    sport = st.sidebar.selectbox("Вид спорта", sports)
    filtered = df[df["sport"] == sport]
    leagues = sorted(filtered["league_name"].dropna().unique())
    league = st.sidebar.selectbox("Лига", leagues)
    filtered = filtered[filtered["league_name"] == league]

    col1, col2, col3 = st.columns(3)
    col1.metric("Матчей", len(filtered))
    col2.metric("Средние голы", round(filtered["total_goals"].mean(), 2))
    col3.metric("Максимум голов", int(filtered["total_goals"].max()))

    fig_ts = px.line(
        filtered.sort_values("event_date"),
        x="event_date",
        y="total_goals",
        markers=True,
        title="Временной ряд: голы в матчах",
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    fig_hist = px.histogram(filtered, x="total_goals", nbins=10, title="Распределение голов")
    st.plotly_chart(fig_hist, use_container_width=True)

    windows = load_windows()
    if not windows.empty:
        st.subheader("Arrow Flight: оконные агрегаты")
        st.dataframe(windows, use_container_width=True)

    st.subheader("Таблица матчей")
    st.dataframe(
        filtered[
            ["event_date", "home_team", "away_team", "home_score", "away_score", "total_goals"]
        ].sort_values("event_date", ascending=False),
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
