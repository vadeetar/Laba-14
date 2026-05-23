"""NATS consumer со скользящим окном 5 минут."""

from __future__ import annotations

import asyncio
import json
import sys
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
WINDOW = timedelta(minutes=5)


class SlidingWindowAggregator:
    def __init__(self) -> None:
        self.events: deque[tuple[datetime, dict]] = deque()

    def add(self, payload: dict) -> None:
        ts_raw = payload.get("collected_at", datetime.now(timezone.utc).isoformat())
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        self.events.append((ts, payload))
        cutoff = datetime.now(timezone.utc) - WINDOW
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()

    def snapshot(self) -> dict:
        if not self.events:
            return {"matches": 0, "avg_goals": 0.0, "leagues": {}, "window_minutes": 5}

        goals = [item[1].get("total_goals", 0) for item in self.events]
        leagues: dict[str, int] = {}
        for _, item in self.events:
            league = item.get("league_name", "unknown")
            leagues[league] = leagues.get(league, 0) + 1

        return {
            "matches": len(self.events),
            "avg_goals": sum(goals) / len(goals),
            "leagues": leagues,
            "window_minutes": WINDOW.total_seconds() / 60,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


async def run(nats_url: str = "nats://127.0.0.1:4222", duration: int = 30) -> None:
    from nats.aio.client import Client as NATS

    aggregator = SlidingWindowAggregator()
    nc = NATS()

    async def handler(msg):
        payload = json.loads(msg.data.decode())
        aggregator.add(payload)

    try:
        await nc.connect(nats_url)
    except Exception as exc:
        print(f"NATS недоступен ({exc}), создаём snapshot из локальных JSONL")
        for file in sorted((ROOT / "data").glob("matches_*.jsonl")):
            with file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        aggregator.add(json.loads(line))
        snapshot = aggregator.snapshot()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "nats_sliding_window.json").write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return

    await nc.subscribe("sports.matches", cb=handler)
    print(f"Подписка на sports.matches ({nats_url}), окно {WINDOW}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    end = asyncio.get_event_loop().time() + duration
    while asyncio.get_event_loop().time() < end:
        snapshot = aggregator.snapshot()
        path = OUTPUT_DIR / "nats_sliding_window.json"
        path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Скользящее окно: {snapshot}")
        await asyncio.sleep(5)

    await nc.drain()


if __name__ == "__main__":
    asyncio.run(run())
