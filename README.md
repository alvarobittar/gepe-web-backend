# gepe-web-backend

Backend HTTP API para GEPE con FastAPI siguiendo buenas prácticas y estructura modular.

## Estructura

```
gepe-web-backend/
└── src/
	├── main.py
	├── routers/
	│   ├── products.py
	│   ├── clubs.py
	│   └── stats.py
	├── models/
	│   ├── __init__.py
	│   └── product.py
	├── schemas/
	│   └── product_schema.py
	├── services/
	│   └── ranking_service.py
	├── database.py
	└── config.py
```

## Requisitos

- Python 3.11+

## Ejecutar localmente (Windows PowerShell)

```powershell
cd C:\Users\Alvaro\Desktop\GEPE-WEB\gepe-web-backend
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --port 4000
```

Abre http://localhost:4000 para ver el endpoint raíz y http://localhost:4000/api/health para el health check.

## Conexión con el frontend (Next.js)

En el proyecto `gepe-web-frontend`:

1. Crear `.env.local` con:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:4000
```

2. El frontend está configurado para proxy a `/api/*` mediante rewrites hacia el backend. Ejemplo: `/api/health` en el navegador llama a `http://localhost:4000/api/health`.

3. Levantar el frontend:

```powershell
cd C:\Users\Alvaro\Desktop\GEPE-WEB\gepe-web-frontend
npm install
npm run dev
```

Open http://localhost:4000/api/health

## CORS

Allowed origin defaults to `http://localhost:3000`. Adjust `CORS_ORIGIN` in `.env` if needed.