"""Полный прогон конвейера лабораторной работы №14, вариант 18."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARTS = ROOT / "charts"
SCREENSHOTS = ROOT / "report" / "screenshots"


def run(cmd: list[str], *, cwd: Path | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd or ROOT).returncode


def main() -> None:
    run([sys.executable, "-m", "pip", "install", "-r", "python/requirements.txt", "-q"])

    if shutil.which("cargo"):
        run(["cargo", "build", "--release"], cwd=ROOT / "rust-validator")

    # Delegate to PowerShell orchestrator when available
    script = ROOT / "run.ps1"
    if script.exists():
        run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)])
    else:
        run([sys.executable, "python/collector_python.py"])
        run([sys.executable, "python/arrow_client.py"])
        run([sys.executable, "python/nats_consumer.py"])
        run([sys.executable, "python/analyze.py"])
        run([sys.executable, "python/benchmark.py"])

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    if CHARTS.exists():
        for chart in CHARTS.glob("*.png"):
            shutil.copy2(chart, SCREENSHOTS / chart.name)

    print("\nГотово.")


if __name__ == "__main__":
    main()
