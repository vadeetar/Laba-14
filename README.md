# Лабораторная работа №14 — вариант 18

**Студент:** Тарасов Вадим Романович | **Группа:** 221131

Сбор и анализ спортивной статистики (футбол + хоккей, TheSportsDB API).

## Быстрый запуск

```powershell
cd "E:\лаба 15"
.\run.ps1
py -3 -m streamlit run python/dashboard.py
```

## Архитектура

```text
Go collector → JSONL / NATS / Arrow Flight → Polars → Parquet → DuckDB → Charts → Streamlit
```

## Структура

| Компонент | Путь |
|-----------|------|
| Go-сборщик | `go-collector/` |
| Python-анализ | `python/analyze.py` |
| Arrow-клиент | `python/arrow_client.py` |
| NATS consumer | `python/nats_consumer.py` |
| Benchmark | `python/benchmark.py` |
| Dashboard | `python/dashboard.py` |
| Rust-валидатор | `rust-validator/` |
| Docker | `docker-compose.yml` |
| Kubernetes HPA | `k8s/deployment.yaml` |
| Отчёт | `report/REPORT.md` |

## Docker

```powershell
docker compose run --rm collector-benchmark   # Go benchmark
docker compose up -d                          # полный стек
py -3 python/arrow_client.py                  # Arrow Flight
```

## Kubernetes

```powershell
.\scripts\deploy_k8s.ps1
```

## Отчёт

- [report/TITLE.md](report/TITLE.md) — титульный лист
- [report/REPORT.md](report/REPORT.md) — полный отчёт
