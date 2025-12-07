# Script para ejecutar el servidor de desarrollo en PowerShell
# Asegúrate de estar en el directorio gepe-web-backend

$ErrorActionPreference = "Stop"

# Cambiar al directorio del script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Verificar si el entorno virtual existe
if (-Not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error al crear el entorno virtual" -ForegroundColor Red
        exit 1
    }
}

# Verificar si las dependencias están instaladas
Write-Host "Verificando e instalando dependencias..." -ForegroundColor Yellow
$pythonExe = Join-Path $scriptDir ".venv\Scripts\python.exe"
& $pythonExe -m pip install --quiet --upgrade pip
& $pythonExe -m pip install --quiet -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error al instalar dependencias" -ForegroundColor Red
    exit 1
}

# Ejecutar uvicorn usando el Python del entorno virtual
Write-Host "Iniciando servidor en http://localhost:8000..." -ForegroundColor Green
Write-Host "Presiona Ctrl+C para detener el servidor" -ForegroundColor Cyan
& $pythonExe -m uvicorn src.main:app --reload --port 8000

