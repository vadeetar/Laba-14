# Лабораторная работа №14 — вариант 18

**Студент:** Тарасов Вадим Романович  
**Группа:** 221131  
**Тема:** Сбор и анализ спортивной статистики (API футбольных и хоккейных лиг)

## Архитектура конвейера

```text
TheSportsDB API
      │
      ▼
Go-сборщик (2 worker через etcd)
  • goroutines + каналы
  • batch JSONL
  • tumbling window
  • NATS (sports.matches / sports.windows)
  • Arrow Flight :8815
      │
      ├── JSONL ──► Polars ──► Parquet ──► DuckDB ──► графики
      ├── NATS ──► Python sliding window (5 мин)
      └── Arrow ──► Python Flight client
                              │
                              ▼
                     Streamlit dashboard
```

## Структура проекта

| Путь | Назначение |
|------|------------|
| `go-collector/` | Распределённый сборщик на Go |
| `python/analyze.py` | Polars + DuckDB + визуализация |
| `python/nats_consumer.py` | Скользящее окно из NATS |
| `python/arrow_client.py` | Клиент Arrow Flight |
| `python/collector_python.py` | Python-сборщик для сравнения |
| `python/dashboard.py` | Streamlit-дашборд |
| `rust-validator/` | Rust-библиотека валидации (cdylib) |
| `docker-compose.yml` | etcd + NATS + 2 Go worker |
| `report/REPORT.md` | Отчёт по лабораторной |

## Быстрый запуск

### 1. Python-зависимости

```powershell
cd "E:\лаба 15"
py -3 -m pip install -r python/requirements.txt
```

### 2. Сбор данных (Docker)

```powershell
docker compose up --build -d
# подождать ~90 секунд, затем остановить
docker compose down
```

Если Docker недоступен:

```powershell
py -3 python/generate_sample_data.py
```

### 3. Анализ

```powershell
py -3 python/analyze.py
py -3 python/collector_python.py
py -3 python/benchmark.py
```

### 4. NATS consumer (если поднят docker compose)

```powershell
py -3 python/nats_consumer.py
```

### 5. Arrow Flight client

```powershell
py -3 python/arrow_client.py
```

### 6. Streamlit-дашборд

```powershell
py -3 -m streamlit run python/dashboard.py
```

## Rust-валидатор

```powershell
cd rust-validator
cargo build --release
```

DLL: `rust-validator/target/release/sports_validator.dll`

## Источник данных

Бесплатный API [TheSportsDB](https://www.thesportsdb.com/):
- English Premier League (`4328`)
- La Liga (`4335`)
- Bundesliga (`4331`)
- NHL (`4380`)

## Пример DuckDB-запроса

```sql
SELECT sport, league_name, AVG(total_goals) AS avg_goals, COUNT(*) AS matches
FROM read_parquet('output/matches_clean.parquet')
GROUP BY sport, league_name
ORDER BY avg_goals DESC;
```
