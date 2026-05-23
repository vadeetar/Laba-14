"""Python-обёртка над Rust-валидатором (fallback на Python при отсутствии DLL)."""

from __future__ import annotations

import ctypes
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_PATH = ROOT / "rust-validator" / "target" / "release" / "sports_validator.dll"


def validate_python(record: dict) -> bool:
    if not record.get("home_team") or not record.get("away_team"):
        return False
    for key in ("home_score", "away_score", "total_goals"):
        value = record.get(key, 0)
        if value is None or value < 0:
            return False
    if record.get("total_goals") != record.get("home_score", 0) + record.get("away_score", 0):
        return False
    return True


def validate_rust(record: dict) -> bool:
    if not LIB_PATH.exists():
        return validate_python(record)

    lib = ctypes.CDLL(str(LIB_PATH))
    lib.validate_match_json.argtypes = [ctypes.c_char_p]
    lib.validate_match_json.restype = ctypes.c_int
    payload = json.dumps(record, ensure_ascii=False).encode("utf-8")
    return bool(lib.validate_match_json(payload))


def validate_batch(records: list[dict]) -> tuple[list[dict], list[dict]]:
    valid, invalid = [], []
    for record in records:
        if validate_rust(record):
            valid.append(record)
        else:
            invalid.append(record)
    return valid, invalid


if __name__ == "__main__":
    sample = {
        "home_team": "Team A",
        "away_team": "Team B",
        "home_score": 2,
        "away_score": 1,
        "total_goals": 3,
    }
    print("valid" if validate_rust(sample) else "invalid")
