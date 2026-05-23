$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Lab 14 full pipeline ==="
py -3 -m pip install -r python/requirements.txt -q

# Rust validator
if (Get-Command cargo -ErrorAction SilentlyContinue) {
    Push-Location rust-validator
    cargo build --release
    Pop-Location
} else {
    Write-Host "cargo not found, validator will use Python fallback unless DLL exists"
}

# Go benchmark via Docker or local Go
if (Get-Command go -ErrorAction SilentlyContinue) {
    Write-Host "Running local Go benchmark..."
    $env:BENCHMARK_MODE = "1"
    $env:OUTPUT_DIR = "data"
    $env:CONFIG_PATH = "config/leagues.json"
    $env:NATS_URL = ""
    $env:ETCD_ENDPOINTS = ""
    Push-Location go-collector
    go build -o collector.exe ./cmd/collector
    .\collector.exe
    Pop-Location
    py -3 python/arrow_client.py
} elseif (docker info 2>$null) {
    docker compose up -d etcd nats
    Start-Sleep -Seconds 3
    docker compose up -d collector-worker-1 collector-worker-2
    Start-Sleep -Seconds 75
    docker compose stop collector-worker-1 collector-worker-2

    Write-Host "Fetching Arrow IPC data..."
    py -3 python/arrow_client.py

    Write-Host "Running NATS consumer..."
    py -3 python/nats_consumer.py
} else {
    Write-Host "Docker unavailable - sample data fallback"
    py -3 python/generate_sample_data.py
    py -3 python/arrow_client.py
    py -3 python/nats_consumer.py
}

py -3 python/collector_python.py
py -3 python/analyze.py
py -3 python/benchmark.py
py -3 python/export_dashboard_preview.py

New-Item -ItemType Directory -Force -Path report/screenshots | Out-Null
Copy-Item charts/*.png report/screenshots/ -ErrorAction SilentlyContinue

Write-Host "Done. Dashboard: py -3 -m streamlit run python/dashboard.py"
