"""Экспорт превью Streamlit-дашборда в PNG для отчёта."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
DATA = ROOT / "data"
SCREENSHOTS = ROOT / "report" / "screenshots"


def load_data() -> pd.DataFrame:
    arrow = OUTPUT / "arrow_matches.parquet"
    if arrow.exists():
        return pd.read_parquet(arrow)
    rows = []
    for file in sorted(DATA.glob("matches_*.jsonl")):
        with file.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    return pd.DataFrame(rows)


def main() -> None:
    df = load_data()
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOTS / "streamlit_dashboard_preview.png"

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Streamlit Dashboard Preview — Lab 14 Variant 18", fontsize=14)

    if df.empty:
        axes[0, 0].text(0.5, 0.5, "No data", ha="center")
    else:
        axes[0, 0].bar(
            df.groupby("league_name")["total_goals"].mean().index,
            df.groupby("league_name")["total_goals"].mean().values,
        )
        axes[0, 0].set_title("Средние голы по лигам")
        axes[0, 0].tick_params(axis="x", rotation=30)

        axes[0, 1].hist(df["total_goals"], bins=8, color="#16a34a")
        axes[0, 1].set_title("Распределение голов")

        ts = df.groupby("event_date")["total_goals"].mean()
        axes[1, 0].plot(ts.index, ts.values, marker="o")
        axes[1, 0].set_title("Временной ряд")
        axes[1, 0].tick_params(axis="x", rotation=45)

        sport_counts = df["sport"].value_counts()
        axes[1, 1].pie(sport_counts.values, labels=sport_counts.index, autopct="%1.1f%%")
        axes[1, 1].set_title("Доля видов спорта")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Dashboard preview: {path}")


if __name__ == "__main__":
    main()
