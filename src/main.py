import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from .routers import products, clubs, stats, cart, user
from .config import get_settings
from .database import Base, engine

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno desde .env (solo en desarrollo local)
# Buscar el .env en el directorio del backend (gepe-web-backend)
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path)

# Importar todos los modelos para que SQLAlchemy los registre antes de create_all()
# Esto asegura que todas las tablas se creen correctamente
from .models.product import Product, Category  # noqa: F401
from .models.user import User  # noqa: F401
from .models.cart import CartItem  # noqa: F401
from .models.order import Order  # noqa: F401

settings = get_settings()

app = FastAPI(title="GEPE Web Backend", version="0.1.0")

# Crear tablas si no existen (para desarrollo / primera versión)
# IMPORTANTE: Todos los modelos deben estar importados antes de esta línea
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

def create_tables():
    """Crea las tablas en la base de datos si no existen."""
    try:
        logger.info("Creando tablas en la base de datos...")
        
        # Obtener lista de tablas que deberían existir
        expected_tables = list(Base.metadata.tables.keys())
        logger.info(f"Tablas esperadas: {', '.join(expected_tables)}")
        
        # Crear todas las tablas
        Base.metadata.create_all(bind=engine)
        
        # Verificar que se crearon correctamente
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        logger.info(f"Tablas existentes en la BD: {', '.join(existing_tables) if existing_tables else '(ninguna)'}")
        
        # Verificar que todas las tablas esperadas existen
        missing_tables = [t for t in expected_tables if t not in existing_tables]
        if missing_tables:
            logger.warning(f"⚠️  Tablas faltantes: {', '.join(missing_tables)}")
        else:
            logger.info("✅ Todas las tablas fueron creadas/verificadas exitosamente")
            
    except Exception as e:
        logger.error(f"❌ ERROR al crear tablas: {str(e)}", exc_info=True)
        raise

# Crear tablas al iniciar
create_tables()

# Include routers
app.include_router(products.router, prefix="/api")
app.include_router(clubs.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(user.router, prefix="/api")


@app.get("/", tags=["root"])  # Simple welcome endpoint
async def root():
    return {"message": "Bienvenido al backend de GEPE Web"}


@app.get("/api/health", tags=["health"])  # Health check for frontend
async def health():
    return {"status": "ok"}
