$ErrorActionPreference = "Stop"

$ContainerName = "pm-mvp-container"

try {
    docker rm -f $ContainerName | Out-Null
} catch {
    # Ignore if the container does not exist.
}

Write-Host "Stopped Project Management MVP container."
