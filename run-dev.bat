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

REM Verificar e instalar dependencias críticas si no están disponibles
echo [INFO] Verificando dependencias...
.venv\Scripts\python -c "import mercadopago" 2>nul
if errorlevel 1 (
    echo [WARN] mercadopago no esta instalado en el venv.
    echo [INFO] Instalando dependencias desde requirements.txt...
    .venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias.
        echo [INFO] Por favor, ejecuta manualmente:
        echo   cd gepe-web-backend
        echo   .venv\Scripts\activate
        echo   pip install -r requirements.txt
        exit /b 1
    )
    echo [INFO] Dependencias instaladas correctamente.
) else (
    REM Verificar email-validator (necesario para EmailStr de Pydantic)
    .venv\Scripts\python -c "import email_validator" 2>nul
    if errorlevel 1 (
        echo [WARN] email-validator no esta instalado.
        echo [INFO] Instalando email-validator...
        .venv\Scripts\pip install email-validator
        if errorlevel 1 (
            echo [WARN] Fallo instalacion directa, intentando desde requirements.txt...
            .venv\Scripts\pip install -r requirements.txt
        )
    )
)

REM Verificar que uvicorn esté instalado (fallback)
.venv\Scripts\python -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo [WARN] uvicorn no esta instalado. Instalando dependencias desde requirements.txt...
    .venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias.
        exit /b 1
    )
)

REM Ejecutar uvicorn con el Python del venv
REM Usar start /b para ejecutar en segundo plano y evitar que el script termine
echo [INFO] Iniciando backend FastAPI...
.venv\Scripts\python -m uvicorn src.main:app --reload --port 8000
