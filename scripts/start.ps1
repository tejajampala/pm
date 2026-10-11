$ErrorActionPreference = "Stop"

$ImageName = "pm-mvp"
$ContainerName = "pm-mvp-container"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

docker build -t $ImageName .
docker run --rm -d --name $ContainerName --env-file (Join-Path $ProjectRoot ".env") -p 8000:8000 $ImageName

Write-Host "Project Management MVP is running at http://localhost:8000"
