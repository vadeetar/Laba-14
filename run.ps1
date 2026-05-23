$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing Python dependencies..."
py -3 -m pip install -r python/requirements.txt -q

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Starting Docker collectors..."
    docker compose up --build -d
    Start-Sleep -Seconds 90
    docker compose down
} else {
    Write-Host "Docker not available, generating sample data..."
    py -3 python/generate_sample_data.py
}

Write-Host "Collecting with Python for benchmark..."
py -3 python/collector_python.py

Write-Host "Running analysis..."
py -3 python/analyze.py
py -3 python/benchmark.py

Write-Host "Done. See output/ and charts/"
