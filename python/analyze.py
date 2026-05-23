"""Загрузка, очистка, агрегация и визуализация спортивной статистики (вариант 18)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import polars as pl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validator import validate_batch, validator_backend  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CHARTS_DIR = ROOT / "charts"


def load_primary_data() -> tuple[pl.DataFrame, str]:
    arrow_path = OUTPUT_DIR / "arrow_matches.parquet"
    if arrow_path.exists():
        print(f"=== Загрузка через Apache Arrow: {arrow_path} ===")
        return pl.read_parquet(arrow_path), "arrow"

    files = sorted(DATA_DIR.glob("matches_*.jsonl"))
    if not files:
        raise FileNotFoundError("Нет arrow_matches.parquet и JSONL в data/")

    rows: list[dict] = []
    for file in files:
        with file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    print("=== Fallback: загрузка JSONL ===")
    return pl.DataFrame(rows), "jsonl"


def inspect(df: pl.DataFrame) -> None:
    print("=== Первые 5 строк ===")
    print(df.head(5))
    print("\n=== Схема и типы ===")
    print(df.schema)
    print(f"\nКоличество строк: {df.height}")
    nulls = {col: df[col].null_count() for col in df.columns}
    print(f"Пропуски по колонкам: {nulls}")


def validate_with_rust(df: pl.DataFrame) -> pl.DataFrame:
    print(f"\n=== Валидация записей ({validator_backend()}) ===")
    records = df.to_dicts()
    valid, invalid = validate_batch(records)
    print(f"Валидных: {len(valid)}, отклонено: {len(invalid)}")
    if invalid:
        print("Примеры отклонённых:", invalid[:3])
    return pl.DataFrame(valid) if valid else df


def clean(df: pl.DataFrame) -> pl.DataFrame:
    print("\n=== Очистка данных ===")
    print(f"1) Удаление дубликатов по event_id: было {df.height} строк")
    df = df.unique(subset=["event_id"], keep="first")
    print(f"   стало {df.height} строк")

    print("2) Удаление строк с пустыми командами")
    df = df.filter(
        (pl.col("home_team").str.len_chars() > 0)
        & (pl.col("away_team").str.len_chars() > 0)
    )

    print("3) Приведение типов и заполнение пропусков")
    df = df.with_columns(
        pl.col("home_score").cast(pl.Int64, strict=False).fill_null(0),
        pl.col("away_score").cast(pl.Int64, strict=False).fill_null(0),
        pl.col("total_goals").cast(pl.Int64, strict=False).fill_null(0),
        pl.col("event_date").cast(pl.Utf8, strict=False).fill_null("unknown"),
        pl.col("sport").cast(pl.Utf8, strict=False).fill_null("unknown"),
    )
    return df


def aggregate(df: pl.DataFrame) -> pl.DataFrame:
    summary = df.group_by(["sport", "league_name"]).agg(
        pl.col("total_goals").sum().alias("sum_goals"),
        pl.col("total_goals").mean().alias("avg_goals"),
        pl.col("total_goals").min().alias("min_goals"),
        pl.col("total_goals").max().alias("max_goals"),
        pl.len().alias("count"),
    ).sort(["sport", "count"], descending=[False, True])

    print("\n=== Агрегация по виду спорта и лиге ===")
    print(summary)
    return summary


def save_parquet(df: pl.DataFrame, path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = path if path.is_absolute() else OUTPUT_DIR / path
    df.write_parquet(target)
    print(f"\nParquet сохранён: {target}")


def duckdb_analysis(parquet_path: Path) -> pl.DataFrame:
    query = f"""
        SELECT
            sport,
            league_name,
            COUNT(*) AS matches,
            ROUND(AVG(total_goals), 2) AS avg_goals,
            MIN(total_goals) AS min_goals,
            MAX(total_goals) AS max_goals
        FROM read_parquet('{parquet_path.as_posix()}')
        WHERE total_goals >= 0
        GROUP BY sport, league_name
        HAVING COUNT(*) >= 1
        ORDER BY avg_goals DESC, matches DESC
    """

    start = time.perf_counter()
    conn = duckdb.connect()
    result = conn.execute(query).pl()
    duck_time = time.perf_counter() - start

    start = time.perf_counter()
    _ = (
        pl.read_parquet(parquet_path)
        .filter(pl.col("total_goals") >= 0)
        .group_by(["sport", "league_name"])
        .agg(
            pl.len().alias("matches"),
            pl.col("total_goals").mean().alias("avg_goals"),
            pl.col("total_goals").min().alias("min_goals"),
            pl.col("total_goals").max().alias("max_goals"),
        )
        .sort(["avg_goals", "matches"], descending=[True, True])
    )
    polars_time = time.perf_counter() - start

    print("\n=== DuckDB SQL-анализ ===")
    print(result)
    print(f"\nВремя DuckDB: {duck_time:.4f} c")
    print(f"Время Polars: {polars_time:.4f} c")

    metrics = {"duckdb_seconds": duck_time, "polars_seconds": polars_time}
    (OUTPUT_DIR / "performance.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return result


def visualize(df: pl.DataFrame, summary: pl.DataFrame) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Bar chart - avg goals by league
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(summary["league_name"].to_list(), summary["avg_goals"].to_list(), color="#2563eb")
    ax.set_title("Среднее количество голов по лигам")
    ax.set_xlabel("Средние голы")
    fig.tight_layout()
    chart1 = CHARTS_DIR / "avg_goals_by_league.png"
    fig.savefig(chart1, dpi=150)
    plt.close(fig)

    # 2. Histogram
    fig, ax = plt.subplots(figsize=(8, 5))
    goals = df["total_goals"].to_list()
    max_goals = max(goals) if goals else 1
    ax.hist(goals, bins=range(0, max_goals + 2), color="#16a34a", edgecolor="white")
    ax.set_title("Распределение общего числа голов в матче")
    ax.set_xlabel("Голы")
    ax.set_ylabel("Количество матчей")
    fig.tight_layout()
    chart2 = CHARTS_DIR / "goals_distribution.png"
    fig.savefig(chart2, dpi=150)
    plt.close(fig)

    # 3. Time series - goals by event date
    ts = (
        df.filter(pl.col("event_date") != "unknown")
        .group_by("event_date")
        .agg(pl.col("total_goals").mean().alias("avg_goals"))
        .sort("event_date")
    )
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ts["event_date"].to_list(), ts["avg_goals"].to_list(), marker="o", color="#9333ea")
    ax.set_title("Временной ряд: средние голы по датам матчей")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Средние голы")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    chart3 = CHARTS_DIR / "goals_time_series.png"
    fig.savefig(chart3, dpi=150)
    plt.close(fig)

    # 4. Pie chart - matches by sport
    sport_counts = df.group_by("sport").len()
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        sport_counts["len"].to_list(),
        labels=sport_counts["sport"].to_list(),
        autopct="%1.1f%%",
        colors=["#2563eb", "#dc2626"],
    )
    ax.set_title("Доля матчей по видам спорта")
    fig.tight_layout()
    chart4 = CHARTS_DIR / "sport_share_pie.png"
    fig.savefig(chart4, dpi=150)
    plt.close(fig)

    print(
        "\nГрафики сохранены:\n"
        f"- {chart1}\n- {chart2}\n- {chart3}\n- {chart4}"
    )


def main() -> None:
    raw, source = load_primary_data()
    print(f"Канал данных: {source}")
    inspect(raw)
    validated = validate_with_rust(raw)
    cleaned = clean(validated)
    summary = aggregate(cleaned)
    parquet_path = OUTPUT_DIR / "matches_clean.parquet"
    save_parquet(cleaned, parquet_path)
    duckdb_analysis(parquet_path)
    visualize(cleaned, summary)


if __name__ == "__main__":
    main()
