"""Streamlit-дашборд спортивной статистики (вариант 18)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"


@st.cache_data
def load_matches() -> pd.DataFrame:
    rows = []
    for file in sorted(DATA_DIR.glob("matches_*.jsonl")):
        with file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    if not rows:
        parquet = OUTPUT_DIR / "matches_clean.parquet"
        if parquet.exists():
            return pd.read_parquet(parquet)
        return pd.DataFrame()
    return pd.DataFrame(rows)


@st.cache_data
def load_windows() -> pd.DataFrame:
    path = OUTPUT_DIR / "arrow_windows.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def main() -> None:
    st.set_page_config(page_title="Спортивная статистика", layout="wide")
    st.title("Лабораторная работа №14 — вариант 18")
    st.caption("Тарасов Вадим Романович, группа 221131")

    df = load_matches()
    if df.empty:
        st.warning("Нет данных. Запустите Go-сборщик или скрипт generate_sample_data.py")
        return

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

    fig1 = px.bar(
        filtered.groupby("home_team")["total_goals"].mean().reset_index(),
        x="home_team",
        y="total_goals",
        title="Среднее число голов по домашним командам",
    )
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.histogram(filtered, x="total_goals", nbins=10, title="Распределение голов")
    st.plotly_chart(fig2, use_container_width=True)

    windows = load_windows()
    if not windows.empty:
        st.subheader("Оконные агрегаты (Arrow Flight)")
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
