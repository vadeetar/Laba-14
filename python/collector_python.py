"""Сборщик на Python (asyncio/aiohttp) для сравнения производительности с Go."""

from __future__ import annotations

import asyncio
import json
import time
import tracemalloc
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "leagues.json"
DATA_DIR = ROOT / "data"
OUTPUT = ROOT / "output" / "python_collector_benchmark.json"


async def fetch_league(session: aiohttp.ClientSession, league: dict) -> list[dict]:
    endpoints = [
        f"https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php?id={league['id']}",
        f"https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id={league['id']}",
    ]
    events: list[dict] = []
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for url in endpoints:
        async with session.get(url, timeout=20) as resp:
            payload = await resp.json()

        for item in payload.get("events") or []:
            home_raw = item.get("intHomeScore")
            away_raw = item.get("intAwayScore")
            home = int(home_raw) if home_raw not in (None, "") else 0
            away = int(away_raw) if away_raw not in (None, "") else 0
            events.append(
                {
                    "event_id": item.get("idEvent"),
                    "league_id": league["id"],
                    "league_name": league["name"],
                    "sport": league["sport"],
                    "home_team": item.get("strHomeTeam"),
                    "away_team": item.get("strAwayTeam"),
                    "home_score": home,
                    "away_score": away,
                    "total_goals": home + away,
                    "event_date": item.get("dateEvent"),
                    "status": item.get("strStatus"),
                    "collected_at": now,
                    "worker_id": "python-collector",
                    "source": "python_async",
                }
            )
    return events


async def collect_all() -> tuple[int, float, float, float, list[dict]]:
    leagues = json.loads(CONFIG.read_text(encoding="utf-8"))["leagues"]
    tracemalloc.start()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_league(session, league) for league in leagues]
        batches = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - wall_start
    cpu_elapsed = time.process_time() - cpu_start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    records = [event for batch in batches for event in batch if event.get("event_id")]
    return len(records), elapsed, cpu_elapsed, peak / (1024 * 1024), records


def save_jsonl(records: list[dict]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"matches_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def main() -> None:
    total, elapsed, cpu_elapsed, peak_mb, records = asyncio.run(collect_all())
    if records:
        saved = save_jsonl(records)
        print(f"JSONL сохранён: {saved}")
    result = {
        "collector": "python_asyncio",
        "events_collected": total,
        "elapsed_seconds": round(elapsed, 4),
        "cpu_seconds": round(cpu_elapsed, 4),
        "peak_memory_mb": round(peak_mb, 2),
        "events_per_second": round(total / elapsed, 2) if elapsed else 0,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
