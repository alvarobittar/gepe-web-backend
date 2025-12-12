from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from ..database import Base


class UniqueVisit(Base):
    """
    Registra visitas únicas al sitio.
    El frontend identifica cada visitante con un session_id único guardado en localStorage.
    """
    __tablename__ = "unique_visits"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
