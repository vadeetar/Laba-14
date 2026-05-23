"""Python-клиент Apache Arrow Flight для получения оконных агрегатов от Go-сборщика."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.flight as flight

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"


def fetch_arrow_windows(host: str = "127.0.0.1", port: int = 8815) -> Path:
    client = flight.connect(f"grpc://{host}:{port}")
    info = client.get_flight_info(flight.FlightDescriptor.for_path("sports_windows"))
    reader = client.do_get(info.endpoints[0].ticket)
    table = reader.read_all()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = OUTPUT_DIR / "arrow_windows.parquet"
    table.to_pandas().to_parquet(parquet_path, index=False)

    json_path = OUTPUT_DIR / "arrow_windows.json"
    json_path.write_text(
        json.dumps(table.to_pydict(), indent=2, default=str),
        encoding="utf-8",
    )

    print(f"Получено {table.num_rows} оконных агрегатов через Arrow Flight")
    print(f"Сохранено: {parquet_path}")
    return parquet_path


if __name__ == "__main__":
    fetch_arrow_windows()
