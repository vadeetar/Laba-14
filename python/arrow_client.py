"""Python-клиент Apache Arrow IPC — основной канал передачи данных."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl
import pyarrow as pa

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"


def read_arrow_ipc(path: Path) -> pl.DataFrame:
    with path.open("rb") as handle:
        reader = pa.ipc.open_stream(handle)
        table = reader.read_all()
    return pl.from_arrow(table)


def jsonl_fallback() -> pl.DataFrame:
    rows: list[dict] = []
    for file in sorted(DATA_DIR.glob("matches_*.jsonl")):
        with file.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    if not rows:
        raise FileNotFoundError("Нет Arrow IPC и JSONL")
    return pl.DataFrame(rows)


def save_arrow_pipeline() -> dict[str, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}

    arrow_matches = DATA_DIR / "matches.arrow"
    if arrow_matches.exists():
        matches = read_arrow_ipc(arrow_matches)
        source = "arrow_ipc"
    else:
        print("Arrow IPC не найден, fallback JSONL -> Parquet")
        matches = jsonl_fallback()
        source = "jsonl_fallback"

    matches_path = OUTPUT_DIR / "arrow_matches.parquet"
    matches.write_parquet(matches_path)
    result["matches"] = matches_path

    arrow_windows = DATA_DIR / "windows.arrow"
    if arrow_windows.exists():
        windows = read_arrow_ipc(arrow_windows)
        windows_path = OUTPUT_DIR / "arrow_windows.parquet"
        windows.write_parquet(windows_path)
        result["windows"] = windows_path

    json_size = sum(f.stat().st_size for f in DATA_DIR.glob("matches_*.jsonl"))
    arrow_size = arrow_matches.stat().st_size if arrow_matches.exists() else 0
    meta = {
        "source": source,
        "matches_rows": matches.height,
        "json_size_bytes": json_size,
        "arrow_size_bytes": arrow_size,
        "parquet_size_bytes": matches_path.stat().st_size,
        "compression_ratio_vs_json": round(arrow_size / json_size, 3) if json_size else None,
    }
    (OUTPUT_DIR / "arrow_transfer_stats.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    print(f"Источник: {source}, матчей: {matches.height}, parquet: {matches_path}")
    return result


if __name__ == "__main__":
    save_arrow_pipeline()
