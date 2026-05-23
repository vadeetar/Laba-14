# Координация сборщиков через etcd

## Где настроено

- **Docker Compose:** сервис `etcd` на порту `2379`
- **Worker 1/2:** переменная `ETCD_ENDPOINTS=etcd:2379`
- **Go-код:** `go-collector/cmd/collector/main.go`
  - `registerWorker()` — регистрация в `/lab14/workers/{worker_id}`
  - `assignedLeagues()` — шардирование лиг между worker'ами

## Алгоритм шардирования

1. Каждый worker при старте записывает ключ `/lab14/workers/worker-N`.
2. Перед сбором worker читает все ключи с префиксом `/lab14/workers/`.
3. Лиги распределяются по формуле: `league_index % workers_count == worker_index`.
4. В лог выводится список назначенных лиг.

## Запуск

```powershell
docker compose up -d etcd nats
docker compose up -d collector-worker-1 collector-worker-2
docker compose logs collector-worker-1 | findstr etcd
```

Пример лога:

```text
connected to etcd at etcd:2379
etcd sharding: worker=worker-1 total_workers=2 assigned=[English Premier League German Bundesliga NHL]
```

## Проверка ключей в etcd

```powershell
docker compose exec etcd etcdctl get --prefix /lab14/workers/
```
