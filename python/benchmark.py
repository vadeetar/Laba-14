"""Сравнение Go vs Python сборщиков на реальных замерах."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
CHARTS = ROOT / "charts"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_go_stats() -> dict:
    for path in (OUTPUT / "go_collector_benchmark.json", ROOT / "data" / "go_collector_benchmark.json"):
        if path.exists():
            stats = load_json(path)
            shutil.copy2(path, OUTPUT / "go_collector_benchmark.json")
            return stats
    return {}


def main() -> None:
    python_stats = load_json(OUTPUT / "python_collector_benchmark.json")
    go_stats = load_go_stats()
    pipeline_stats = load_json(OUTPUT / "performance.json")
    arrow_stats = load_json(OUTPUT / "arrow_transfer_stats.json")

    if not go_stats:
        print("Предупреждение: go_collector_benchmark.json не найден. Запустите Go benchmark.")

    report = {
        "python": python_stats,
        "go": go_stats,
        "analysis_pipeline": pipeline_stats,
        "arrow_transfer": arrow_stats,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "benchmark_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if python_stats and go_stats:
        CHARTS.mkdir(parents=True, exist_ok=True)
        labels = ["Python asyncio", "Go goroutines"]
        elapsed = [python_stats.get("elapsed_seconds", 0), go_stats.get("elapsed_seconds", 0)]
        memory = [python_stats.get("peak_memory_mb", 0), go_stats.get("peak_memory_mb", 0)]
        throughput = [python_stats.get("events_per_second", 0), go_stats.get("events_per_second", 0)]

        fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        axes[0].bar(labels, elapsed, color=["#f97316", "#2563eb"])
        axes[0].set_title("Время сбора (с)")
        axes[1].bar(labels, memory, color=["#f97316", "#2563eb"])
        axes[1].set_title("Память (MB)")
        axes[2].bar(labels, throughput, color=["#f97316", "#2563eb"])
        axes[2].set_title("Событий/с")
        fig.tight_layout()
        fig.savefig(CHARTS / "go_vs_python_benchmark.png", dpi=150)
        plt.close(fig)
        print(f"График сохранён: {CHARTS / 'go_vs_python_benchmark.png'}")

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
