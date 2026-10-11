$ErrorActionPreference = "Stop"

$ImageName = "pm-mvp"
$ContainerName = "pm-mvp-container"
$VolumeName = "pm-mvp-data"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

docker build -t $ImageName .
docker run --rm -d --name $ContainerName --env-file (Join-Path $ProjectRoot ".env") -p 127.0.0.1:8000:8000 -v "${VolumeName}:/app/backend/data" $ImageName

Write-Host "Project Management MVP is running at http://localhost:8000"
