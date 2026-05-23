# Отчёт по лабораторной работе №14

> Титульный лист: [TITLE.md](TITLE.md)

## 1. Техническое задание

**Вариант 18:** сбор и анализ спортивной статистики из API футбольных/хоккейных лиг (TheSportsDB).

**Студент:** Тарасов Вадим Романович, группа 221131.

**Цель:** ETL-конвейер Go (сбор) → Arrow/NATS → Python (Polars, DuckDB, визуализация, Streamlit).

---

## 2. Выполнение заданий

### Базовые задания (1–10)

| № | Задание | Реализация |
|---|---------|------------|
| 1 | Go-сборщик, goroutines, JSONL | `go-collector/cmd/collector/main.go` |
| 2 | Буфер + пакетная запись | `eventsCh`, `BATCH_SIZE`, `BATCH_FLUSH` |
| 3 | Graceful shutdown | SIGINT/SIGTERM + flush буфера |
| 4 | Polars import | `python/analyze.py` → первые 5 строк, типы, пропуски |
| 5 | Очистка + валидация | Polars + Rust-валидатор (`validator.py`) |
| 6 | Агрегация SUM/AVG/MIN/MAX/COUNT | По `sport + league_name` |
| 7 | Parquet | `output/matches_clean.parquet` |
| 8 | DuckDB SQL + сравнение с Polars | `output/performance.json` |
| 9 | ≥2 визуализации | 4 графика в `charts/` |
| 10 | README | `README.md` |

### Повышенный уровень

| № | Задание | Реализация |
|---|---------|------------|
| 1 | etcd, 2 worker | `docker-compose.yml`, шардирование лиг |
| 2 | Tumbling window в Go | 60 сек → `window_aggregates.jsonl`, NATS |
| 3 | Apache Arrow IPC | Go `matches.arrow` + `python/arrow_client.py` |
| 4 | Rust-валидатор | `rust-validator/`, интеграция в `analyze.py` |
| 5 | Docker + K8s HPA | `Dockerfile`, `k8s/deployment.yaml`, `scripts/deploy_k8s.ps1` |
| — | Go vs Python benchmark | `go_collector_benchmark.json`, `benchmark.py` |
| — | NATS + sliding window 5 мин | `nats_consumer.py` |
| 6 | Streamlit real-time | `dashboard.py` + `streamlit-autorefresh` |

---

## 3. Архитектура

```text
TheSportsDB API
      │
      ▼
Go workers (etcd shard) ──► JSONL (backup)
      │         │
      │         ├── NATS sports.matches ──► Python sliding window
      │         └── Arrow IPC (.arrow) ──► arrow_matches.parquet
      ▼
Polars + Rust validate ──► Parquet ──► DuckDB ──► charts/
      ▼
Streamlit dashboard (auto-refresh)
```

---

## 4. Производительность

Результаты в `output/benchmark_report.json`:
- **Go:** `output/go_collector_benchmark.json` (реальный замер через Docker)
- **Python:** `output/python_collector_benchmark.json`
- **Arrow vs JSON:** `output/arrow_transfer_stats.json`
- **Polars vs DuckDB:** `output/performance.json`

График: `charts/go_vs_python_benchmark.png`

---

## 5. Скриншоты

Графики продублированы в `report/screenshots/`:
- `avg_goals_by_league.png`
- `goals_distribution.png`
- `goals_time_series.png`
- `sport_share_pie.png`
- `go_vs_python_benchmark.png`

---

## 6. Запуск

```powershell
cd "E:\лаба 15"
.\run.ps1
py -3 -m streamlit run python/dashboard.py
```

---

## 7. Выводы

1. Go-сборщик с goroutines обеспечивает более высокую скорость сбора спортивных данных.
2. Apache Arrow Flight снижает объём передаваемых данных относительно JSON.
3. Tumbling/sliding windows позволяют агрегировать поток матчей до анализа.
4. Rust-валидатор повышает надёжность очистки данных на этапе ETL.
5. Streamlit-дашборд с автообновлением отображает актуальную статистику лиг.

---

## 8. Источники

1. https://go.dev/doc/effective_go#concurrency
2. https://pola.rs/
3. https://duckdb.org/
4. https://arrow.apache.org/
5. https://www.thesportsdb.com/api.php
6. https://nats.io/
7. https://etcd.io/
