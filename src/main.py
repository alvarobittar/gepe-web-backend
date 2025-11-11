from fastapi import FastAPI
from .routers import products, clubs, stats
from .config import get_settings

settings = get_settings()

app = FastAPI(title="GEPE Web Backend", version="0.1.0")

# Include routers
app.include_router(products.router, prefix="/api")
app.include_router(clubs.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/", tags=["root"])  # Simple welcome endpoint
async def root():
    return {"message": "Bienvenido al backend de GEPE Web"}


@app.get("/api/health", tags=["health"])  # Health check for frontend
async def health():
    return {"status": "ok"}
