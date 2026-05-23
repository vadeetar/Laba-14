"""Генерация демонстрационных данных, если сборщик ещё не успел записать JSONL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SAMPLE = [
    ("4328", "English Premier League", "football", "Arsenal", "Chelsea", 2, 1),
    ("4328", "English Premier League", "football", "Liverpool", "Manchester City", 1, 1),
    ("4335", "Spanish La Liga", "football", "Real Madrid", "Barcelona", 3, 2),
    ("4331", "German Bundesliga", "football", "Bayern", "Dortmund", 4, 0),
    ("4380", "NHL", "hockey", "Boston Bruins", "Toronto Maple Leafs", 3, 2),
    ("4380", "NHL", "hockey", "New York Rangers", "Pittsburgh Penguins", 1, 4),
]


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    path = DATA / f"matches_{now.strftime('%Y%m%d_%H%M%S')}.jsonl"

    with path.open("w", encoding="utf-8") as handle:
        for idx, (league_id, league_name, sport, home, away, hs, aws) in enumerate(SAMPLE):
            event = {
                "event_id": f"demo-{idx + 1}",
                "league_id": league_id,
                "league_name": league_name,
                "sport": sport,
                "home_team": home,
                "away_team": away,
                "home_score": hs,
                "away_score": aws,
                "total_goals": hs + aws,
                "event_date": (now - timedelta(days=idx)).date().isoformat(),
                "status": "Match Finished",
                "collected_at": now.isoformat(),
                "worker_id": "demo",
                "source": "sample_generator",
            }
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    window_path = DATA / "window_aggregates.jsonl"
    with window_path.open("w", encoding="utf-8") as handle:
        for league_id, league_name, sport, *_ in SAMPLE[:4]:
            agg = {
                "window_start": (now - timedelta(minutes=1)).isoformat(),
                "window_end": now.isoformat(),
                "league_id": league_id,
                "league_name": league_name,
                "sport": sport,
                "match_count": 2,
                "avg_goals": 2.5,
                "min_goals": 1,
                "max_goals": 4,
                "sum_goals": 5,
                "worker_id": "demo",
            }
            handle.write(json.dumps(agg, ensure_ascii=False) + "\n")

    print(f"Создан файл: {path}")


if __name__ == "__main__":
    main()
