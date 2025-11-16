@echo off
REM Script para ejecutar el backend con el entorno virtual
REM Este archivo debe estar en gepe-web-backend/

cd /d "%~dp0"

REM Verificar si existe el entorno virtual
if not exist .venv (
    echo [ERROR] El entorno virtual no existe.
    echo.
    echo Por favor, crea el entorno virtual primero:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    exit /b 1
)

REM Verificar si uvicorn está instalado
.venv\Scripts\python -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo [WARN] uvicorn no esta instalado en el venv.
    echo [INFO] Instalando dependencias...
    .venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias.
        exit /b 1
    )
)

REM Ejecutar uvicorn con el Python del venv
echo [INFO] Iniciando backend FastAPI...
.venv\Scripts\python -m uvicorn src.main:app --reload --port 8000

