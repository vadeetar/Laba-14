# Развёртывание в minikube (повышенный уровень)

Set-Location $PSScriptRoot/..

if (-not (Get-Command minikube -ErrorAction SilentlyContinue)) {
    Write-Error "minikube не установлен. См. https://minikube.sigs.k8s.io/docs/start/"
}

Write-Host "Building Docker image..."
docker build -t lab14-sports-collector:latest -f go-collector/Dockerfile .

Write-Host "Starting minikube..."
minikube start

Write-Host "Loading image into minikube..."
minikube image load lab14-sports-collector:latest

Write-Host "Applying manifests..."
kubectl apply -f k8s/deployment.yaml

Write-Host "HPA status:"
kubectl get hpa
kubectl get pods

Write-Host "Для доступа: minikube service sports-collector --url"
