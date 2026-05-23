# Лабораторная работа №14

## Данные студента

- **ФИО:** Тарасов Вадим Романович
- **Группа:** 221131
- **Вариант:** 18
- **Номер лабораторной:** 14
- **Сложность:** повышенная

**Тема:** Сбор и анализ спортивной статистики (футбол + хоккей, TheSportsDB API).

---

## Быстрый запуск

```powershell
cd "E:\лаба 15"
.\run.ps1
py -3 -m streamlit run python/dashboard.py
```

## Архитектура

```text
Go workers + etcd → JSONL / NATS / Arrow IPC → Polars → Parquet → DuckDB → Charts → Streamlit
```

## etcd (распределённый сбор)

Сервис **etcd** описан в `docker-compose.yml` (порт 2379). Два worker шардируют лиги через ключи `/lab14/workers/`.

Подробнее: [docs/ETCD.md](docs/ETCD.md)

## Структура

| Компонент | Путь |
|-----------|------|
| Go-сборщик | `go-collector/` |
| etcd docs | `docs/ETCD.md` |
| Python-анализ | `python/analyze.py` |
| Arrow IPC клиент | `python/arrow_client.py` |
| NATS consumer | `python/nats_consumer.py` |
| Benchmark | `python/benchmark.py` |
| Dashboard | `python/dashboard.py` |
| Rust-валидатор | `rust-validator/` |
| Docker | `docker-compose.yml` |
| Kubernetes HPA | `k8s/deployment.yaml` |
| Чеклист методички | `report/METHODOLOGY_CHECKLIST.md` |
| Отчёт | `report/REPORT.md` |

## Docker

```powershell
docker compose up -d etcd nats collector-worker-1 collector-worker-2
docker compose logs collector-worker-1 | findstr etcd
docker compose run --rm collector-benchmark
py -3 python/arrow_client.py
```

## Kubernetes

```powershell
.\scripts\deploy_k8s.ps1
```

## Отчёт

- [report/TITLE.md](report/TITLE.md) — титульный лист  
- [report/REPORT.md](report/REPORT.md) — полный отчёт (9 разделов)  
- [report/METHODOLOGY_CHECKLIST.md](report/METHODOLOGY_CHECKLIST.md) — соответствие методичке
