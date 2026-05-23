# Соответствие методичке — вариант 18 (повышенный уровень)

| Требование методички | Статус | Файл / артефакт |
|---------------------|--------|-----------------|
| Go-сборщик, goroutines | ✅ | `go-collector/cmd/collector/main.go` |
| Буфер + пакетная запись | ✅ | `eventsCh`, `BATCH_SIZE`, `BATCH_FLUSH` |
| Graceful shutdown SIGINT/SIGTERM | ✅ | `main.go` → `signal.Notify` |
| Polars: загрузка, типы, пропуски | ✅ | `python/analyze.py` |
| Очистка, дубликаты, типы | ✅ | `clean()` в `analyze.py` |
| Rust-валидация | ✅ | `rust-validator/`, `validator.py`, `analyze.py` |
| Агрегация SUM/AVG/MIN/MAX/COUNT | ✅ | `aggregate()` |
| Parquet | ✅ | `output/matches_clean.parquet` |
| DuckDB SQL + сравнение Polars | ✅ | `duckdb_analysis()`, `performance.json` |
| ≥2 графика | ✅ | 4 PNG в `charts/` |
| README | ✅ | `README.md` |
| **etcd распределённый сбор** | ✅ | `docker-compose.yml`, `docs/ETCD.md`, `assignedLeagues()` |
| Tumbling window в Go | ✅ | `runWindowAggregator()`, `window_aggregates.jsonl` |
| Apache Arrow (RecordBatch/IPC) | ✅ | `arrow_ipc.go`, `python/arrow_client.py` |
| Rust-библиотека валидации | ✅ | `rust-validator/src/lib.rs` |
| Docker + K8s HPA | ✅ | `Dockerfile`, `k8s/deployment.yaml` |
| Go vs Python benchmark | ✅ | `benchmark.py`, `*_collector_benchmark.json` |
| NATS + sliding window 5 мин | ✅ | `nats_consumer.py` |
| Streamlit real-time | ✅ | `dashboard.py`, `streamlit-autorefresh` |
| Замеры: время, память, CPU | ✅ | `cpu_seconds` в benchmark JSON + график |
| Объём данных JSON vs Arrow | ✅ | `arrow_transfer_stats.json` |
| Отчёт 9 разделов | ✅ | `report/TITLE.md`, `report/REPORT.md` |
| Скриншоты | ✅ | `report/screenshots/` |

## Замечание по etcd

Сервис **etcd присутствует** в `docker-compose.yml` (строки 2–9). Worker'ы подключаются через `ETCD_ENDPOINTS=etcd:2379`. Подробности: [docs/ETCD.md](../docs/ETCD.md).

## Замечание по Apache Arrow

Используется **Arrow IPC** (`matches.arrow`) — формат RecordBatch, разрешённый методичкой («Flight RPC **или** RecordBatch»).
