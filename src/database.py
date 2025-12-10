# Configuración de base de datos usando SQLAlchemy.
# 
# ESTRATEGIA DE BASE DE DATOS:
# - DESARROLLO LOCAL: Usa SQLite local (gepe.db) por defecto (GRATIS, no consume créditos Railway)
# - PRODUCCIÓN/RAILWAY: Usa PostgreSQL de Railway (solo si DATABASE_URL está configurada)
#
# Para desarrollo local con Railway PostgreSQL (gasta créditos):
#   Configura DATABASE_URL en .env con tu URL de Railway
#
# Para desarrollo local con SQLite (GRATIS, recomendado):
#   NO configures DATABASE_URL o déjala vacía/comentada en .env

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Cargar variables de entorno desde .env (solo en desarrollo local)
# Buscar el .env en el directorio del backend (gepe-web-backend)
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path)

# Determinar qué base de datos usar
# Por defecto usa SQLite local (gratis para desarrollo)
# Solo usa Railway PostgreSQL si DATABASE_URL está explícitamente configurada
env_database_url = os.getenv("DATABASE_URL", "").strip()

IS_POSTGRES = env_database_url and not env_database_url.startswith("sqlite")

if IS_POSTGRES:
    # Usar PostgreSQL de Railway o externa si está configurada
    DATABASE_URL = env_database_url
    print("[INFO] Usando PostgreSQL externa (Railway/configurada)")
else:
    # Usar SQLite local para desarrollo (GRATIS, no consume créditos)
    DATABASE_URL = "sqlite:///./gepe.db"
    print("[INFO] Usando SQLite local para desarrollo (gratis, no consume créditos Railway)")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def fix_sequences():
    """
    Arregla las secuencias de PostgreSQL para que usen max(id)+1.
    Esto soluciona errores de "duplicate key value violates unique constraint"
    cuando la secuencia está desincronizada de los datos existentes.
    
    Solo aplica a PostgreSQL - SQLite no tiene este problema.
    """
    if not IS_POSTGRES:
        return
    
    print("[INFO] Verificando y arreglando secuencias de PostgreSQL...")
    
    tables_to_fix = ["orders", "users", "order_items"]
    
    try:
        with engine.connect() as conn:
            for table in tables_to_fix:
                try:
                    # Verificar si la tabla existe
                    result = conn.execute(text(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{table}'
                        )
                    """))
                    exists = result.scalar()
                    
                    if not exists:
                        continue
                    
                    # Resetear la secuencia al max(id) + 1
                    conn.execute(text(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table}', 'id'),
                            COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
                            false
                        )
                    """))
                    conn.commit()
                    print(f"[INFO] Secuencia de '{table}' sincronizada correctamente")
                    
                except Exception as e:
                    print(f"[WARN] No se pudo arreglar secuencia de '{table}': {e}")
                    
    except Exception as e:
        print(f"[WARN] Error al arreglar secuencias: {e}")


def get_db():
  """
  Dependencia para inyectar la sesión de DB en los endpoints de FastAPI.
  """
  db = SessionLocal()
  try:
      yield db
  finally:
      db.close()
