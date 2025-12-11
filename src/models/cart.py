from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)

    # Usuario autenticado (opcional, tiene prioridad sobre session_id)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    calidad = Column(String(50), nullable=True)  # PROFESIONAL, JUGADOR, HINCHA
    talle = Column(String(20), nullable=True)  # S, M, L, XL, etc.

    # Sesión anónima (usado cuando user_id es null)
    session_id = Column(String(255), nullable=True, index=True)
    
    # Timestamp para limpieza de carritos viejos
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")



