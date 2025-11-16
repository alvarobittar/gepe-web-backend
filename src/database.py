# Configuración de base de datos usando SQLAlchemy.
# En Railway se debe configurar la variable de entorno DATABASE_URL
# apuntando al PostgreSQL proporcionado por el servicio.

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Cargar variables de entorno desde .env (solo en desarrollo local)
# Buscar el .env en el directorio del backend (gepe-web-backend)
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gepe.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
  """
  Dependencia para inyectar la sesión de DB en los endpoints de FastAPI.
  """
  db = SessionLocal()
  try:
      yield db
  finally:
      db.close()
