import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import (
    products,
    clubs,
    stats,
    cart,
    user,
    promo_banner,
    hero_media,
    payments,
    orders,
    categories,
    payment_details,
    settings,
    addresses,
    returns,
)
from .config import get_settings, clear_settings_cache
from .database import Base, engine, fix_sequences

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env (solo en desarrollo local)
# Buscar el .env en el directorio del backend (gepe-web-backend)
backend_dir = Path(__file__).parent.parent  # gepe-web-backend/src -> gepe-web-backend
env_path = backend_dir / ".env"
loaded = load_dotenv(dotenv_path=env_path)
if loaded:
    logger.info(f"Variables de entorno cargadas desde: {env_path}")
else:
    logger.warning(f"No se pudo cargar archivo .env desde: {env_path}")

# Limpiar cache de settings para asegurar que se recarguen las variables
clear_settings_cache()

# Importar todos los modelos para que SQLAlchemy los registre antes de create_all()
# Esto asegura que todas las tablas se creen correctamente
from .models.product import Product, Category, ProductSizeStock  # noqa: F401
from .models.product_price_settings import ProductPriceSettings  # noqa: F401
from .models.user import User  # noqa: F401
from .models.address import Address  # noqa: F401
from .models.cart import CartItem  # noqa: F401
from .models.order import Order  # noqa: F401
from .models.payment import Payment  # noqa: F401
from .models.promo_banner import PromoBanner  # noqa: F401
from .models.promo_banner_settings import PromoBannerSettings  # noqa: F401
from .models.club import Club  # noqa: F401
from .models.notification_email import NotificationEmail  # noqa: F401
from .models.hero_media import HeroMedia  # noqa: F401

app_settings = get_settings()
logger.info(f"🔧 CORS_ORIGIN configurado al iniciar: {app_settings.cors_origin}")

app = FastAPI(title="GEPE Web Backend", version="0.1.0", redirect_slashes=False)

# Configurar CORS
# Construir lista de orígenes permitidos dinámicamente
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]

# Verificar si CORS_ORIGIN está realmente configurado (no es el default)
cors_origin_env = os.getenv("CORS_ORIGIN", "")
cors_origin_configured = cors_origin_env and cors_origin_env != "http://localhost:3000"

# Agregar CORS_ORIGIN del .env si está configurado y no está duplicado
if cors_origin_configured:
    # Permitir múltiples orígenes separados por coma
    cors_origins = [origin.strip() for origin in cors_origin_env.split(",")]
    for origin in cors_origins:
        if origin and origin not in allowed_origins:
            allowed_origins.append(origin)

# En producción, permitir todos los orígenes si no hay CORS_ORIGIN configurado explícitamente
# Esto es necesario para Railway donde el frontend puede estar en diferentes dominios
if app_settings.environment == "production" and not cors_origin_configured:
    logger.warning("⚠️ CORS_ORIGIN no configurado en producción, permitiendo todos los orígenes")
    allowed_origins = ["*"]

logger.info(f"🌐 Orígenes CORS permitidos: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas si no existen (para desarrollo / primera versión)
# IMPORTANTE: Todos los modelos deben estar importados antes de esta línea
from sqlalchemy import inspect, text

def create_tables():
    """Crea las tablas en la base de datos si no existen."""
    try:
        logger.info("Creando tablas en la base de datos...")
        
        # Obtener lista de tablas que deberían existir
        expected_tables = list(Base.metadata.tables.keys())
        logger.info(f"Tablas esperadas: {', '.join(expected_tables)}")
        
        # Crear todas las tablas
        Base.metadata.create_all(bind=engine)
        
        # Migrar columnas faltantes en orders si es necesario
        try:
            inspector = inspect(engine)
            if "orders" in inspector.get_table_names():
                # Verificar columnas existentes
                orders_columns = [col["name"] for col in inspector.get_columns("orders")]
                required_columns = {
                    "order_number": "VARCHAR(20)",
                    "external_reference": "VARCHAR(100)",
                    "payment_id": "VARCHAR(100)",
                    "customer_email": "VARCHAR(255)",
                    "customer_name": "VARCHAR(255)",
                    "customer_phone": "VARCHAR(50)",
                    "customer_dni": "VARCHAR(50)",
                    "shipping_method": "VARCHAR(50)",
                    "shipping_address": "VARCHAR(500)",
                    "shipping_city": "VARCHAR(100)",
                    "shipping_province": "VARCHAR(120)",
                    "tracking_code": "VARCHAR(100)",
                    "tracking_company": "VARCHAR(150)",
                    "tracking_branch_address": "VARCHAR(300)",
                    "tracking_attachment_url": "VARCHAR(500)",
                    "production_status": "VARCHAR(50)",  # Micro-estado de producción
                    "created_at": "DATETIME",
                    "updated_at": "DATETIME",
                }
                
                with engine.connect() as conn:
                    for col_name, col_type in required_columns.items():
                        if col_name not in orders_columns:
                            try:
                                conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"✅ Columna agregada: {col_name}")
                            except Exception as e:
                                logger.warning(f"⚠️ No se pudo agregar columna {col_name}: {e}")
                    
                    # Crear índices si no existen
                    try:
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_external_reference ON orders(external_reference)"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_payment_id ON orders(payment_id)"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_order_number ON orders(order_number)"))
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"⚠️ Error al crear índices: {e}")
                    
                    # Generar order_number para órdenes existentes que no lo tengan
                    try:
                        orders_without_number = conn.execute(
                            text("SELECT id FROM orders WHERE order_number IS NULL")
                        ).fetchall()
                        if orders_without_number:
                            logger.info(f"Generando order_number para {len(orders_without_number)} órdenes existentes...")
                            # Importar función de generación de order_number
                            import secrets
                            import string
                            def generate_order_number():
                                """Genera un número de pedido único y no secuencial."""
                                chars = string.ascii_uppercase + string.digits
                                random_code = ''.join(secrets.choice(chars) for _ in range(6))
                                return f"GEPE-{random_code}"
                            
                            for (order_id,) in orders_without_number:
                                order_number = generate_order_number()
                                # Asegurar unicidad
                                while conn.execute(
                                    text("SELECT id FROM orders WHERE order_number = :order_number"),
                                    {"order_number": order_number}
                                ).fetchone():
                                    order_number = generate_order_number()
                                conn.execute(
                                    text("UPDATE orders SET order_number = :order_number WHERE id = :id"),
                                    {"order_number": order_number, "id": order_id}
                                )
                            conn.commit()
                            logger.info("✅ order_number generado para órdenes existentes.")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudieron generar order_number para órdenes existentes: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Error durante migración de orders: {e}")
        
        # Migrar columnas faltantes en cart_items si es necesario
        try:
            inspector = inspect(engine)
            if "cart_items" in inspector.get_table_names():
                cart_items_columns = {col["name"]: col["type"] for col in inspector.get_columns("cart_items")}

                # Determinar el tipo de columna según la base de datos actual
                db_url = str(engine.url)
                if db_url.startswith("sqlite"):
                    # SQLite usa TEXT en lugar de VARCHAR
                    required_cart_columns = {
                        "calidad": "TEXT",
                        "talle": "TEXT",
                    }
                else:
                    # PostgreSQL y otras bases de datos
                    required_cart_columns = {
                        "calidad": "VARCHAR(50)",
                        "talle": "VARCHAR(20)",
                    }
                
                with engine.connect() as conn:
                    for col_name, col_type in required_cart_columns.items():
                        if col_name not in cart_items_columns:
                            try:
                                conn.execute(text(f"ALTER TABLE cart_items ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"✅ Columna agregada a cart_items: {col_name}")
                            except Exception as e:
                                logger.warning(f"⚠️ No se pudo agregar columna {col_name} a cart_items: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Error durante migración de cart_items: {e}")

        # Migrar columnas faltantes en products (preview, imágenes, precios por calidad) si es necesario
        try:
            inspector = inspect(engine)
            if "products" in inspector.get_table_names():
                products_columns = {col["name"]: col["type"] for col in inspector.get_columns("products")}

                db_url = str(engine.url)
                # Para SQLite usamos TEXT, para otros VARCHAR(500)
                if db_url.startswith("sqlite"):
                    img_type = "TEXT"
                else:
                    img_type = "VARCHAR(500)"

                required_product_columns = {
                    "preview_image_url": img_type,
                    "image1_url": img_type,
                    "image2_url": img_type,
                    "image3_url": img_type,
                    "image4_url": img_type,
                    "price_hincha": "FLOAT",
                    "price_jugador": "FLOAT",
                    "price_profesional": "FLOAT",
                    "manual_sales_adjustment": "INTEGER DEFAULT 0",
                }

                with engine.connect() as conn:
                    for col_name, col_type in required_product_columns.items():
                        if col_name not in products_columns:
                            try:
                                conn.execute(text(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"✅ Columna agregada a products: {col_name}")
                            except Exception as e:
                                logger.warning(f"⚠️ No se pudo agregar columna {col_name} a products: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Error durante migración de products: {e}")

        # Migrar columnas faltantes en hero_media (focus point, show_overlay) si es necesario
        try:
            inspector = inspect(engine)
            if "hero_media" in inspector.get_table_names():
                hero_media_columns = {col["name"]: col["type"] for col in inspector.get_columns("hero_media")}

                required_hero_columns = {
                    "image_focus_x": "INTEGER DEFAULT 50",
                    "image_focus_y": "INTEGER DEFAULT 50",
                    "image_zoom": "INTEGER DEFAULT 100",
                    "show_overlay": "BOOLEAN DEFAULT TRUE",
                    "aspect_ratio_desktop": "VARCHAR(10) DEFAULT '16:6'",
                    "aspect_ratio_mobile": "VARCHAR(10) DEFAULT '4:3'",
                    "link_url": "VARCHAR(500)",
                }

                with engine.connect() as conn:
                    for col_name, col_type in required_hero_columns.items():
                        if col_name not in hero_media_columns:
                            try:
                                # SQLite usa INTEGER para BOOLEAN
                                db_url = str(engine.url)
                                if db_url.startswith("sqlite") and col_type.startswith("BOOLEAN"):
                                    col_type = "INTEGER DEFAULT 1"
                                conn.execute(text(f"ALTER TABLE hero_media ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"✅ Columna agregada a hero_media: {col_name}")
                            except Exception as e:
                                logger.warning(f"⚠️ No se pudo agregar columna {col_name} a hero_media: {e}")
                    
                    # Extend video_url column size to accommodate long Instagram URLs
                    try:
                        conn.execute(text("ALTER TABLE hero_media ALTER COLUMN video_url TYPE VARCHAR(2000)"))
                        conn.commit()
                        logger.info("✅ Columna video_url extendida a VARCHAR(2000)")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo extender video_url: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Error durante migración de hero_media: {e}")

        # Inicializar precios globales si la tabla existe pero está vacía
        try:
            from .models.product_price_settings import ProductPriceSettings
            inspector = inspect(engine)
            if "product_price_settings" in inspector.get_table_names():
                with engine.connect() as conn:
                    existing_settings = conn.execute(
                        text("SELECT id FROM product_price_settings WHERE id = 1")
                    ).fetchone()
                    if not existing_settings:
                        logger.info("Creando valores por defecto para precios globales...")
                        conn.execute(text(
                            "INSERT INTO product_price_settings (id, price_hincha, price_jugador, price_profesional) "
                            "VALUES (1, 59900.0, 69900.0, 89900.0)"
                        ))
                        conn.commit()
                        logger.info("✅ Valores por defecto para precios globales creados")
        except Exception as e:
            logger.warning(f"⚠️ Error durante inicialización de precios globales: {e}")
        
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

# Crear tablas al iniciar (no bloquear el inicio si falla)
try:
    create_tables()
    # Arreglar secuencias de PostgreSQL (solo aplica a PostgreSQL)
    fix_sequences()
except Exception as e:
    logger.error(f"❌ Error al crear tablas al iniciar: {str(e)}", exc_info=True)
    logger.warning("⚠️ El servidor continuará iniciando, pero algunas funcionalidades pueden no estar disponibles")

# Include routers
app.include_router(products.router, prefix="/api")
app.include_router(clubs.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(promo_banner.router, prefix="/api")
app.include_router(hero_media.router, prefix="/api")
app.include_router(payments.router, prefix="/api/payments")
app.include_router(orders.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(payment_details.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(addresses.router, prefix="/api")
app.include_router(returns.router, prefix="/api")


@app.get("/", tags=["root"])  # Simple welcome endpoint
async def root():
    logger.info("📍 Request recibido en /")
    return {"message": "Bienvenido al backend de GEPE Web"}


@app.get("/api/health", tags=["health"])  # Health check for frontend
async def health():
    logger.info("💓 Health check recibido")
    return {"status": "ok", "server": "alive"}


@app.get("/api/ping", tags=["health"])  # Super simple test
async def ping():
    import time
    logger.info(f"🏓 Ping recibido a las {time.time()}")
    return {"pong": True, "time": time.time()}


@app.get("/favicon.ico", tags=["static"])
async def favicon():
    """Handle favicon.ico requests - return 204 No Content"""
    from fastapi.responses import Response
    return Response(status_code=204)
