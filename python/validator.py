"""Python-обёртка над Rust-валидатором (ctypes) с fallback."""

from __future__ import annotations

import ctypes
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "rust-validator" / "target" / "release"


def _library_path() -> Path | None:
    if platform.system() == "Windows":
        path = TARGET / "sports_validator.dll"
    elif platform.system() == "Darwin":
        path = TARGET / "libsports_validator.dylib"
    else:
        path = TARGET / "libsports_validator.so"
    return path if path.exists() else None


def validator_backend() -> str:
    return "rust" if _library_path() else "python"


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
    lib_path = _library_path()
    if lib_path is None:
        return validate_python(record)

    lib = ctypes.CDLL(str(lib_path))
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
