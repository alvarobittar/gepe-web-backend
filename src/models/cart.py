from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship

from ..database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)

    # En esta primera versión usamos un único usuario "invitado" por simplicidad.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    calidad = Column(String(50), nullable=True)  # PROFESIONAL, JUGADOR, HINCHA
    talle = Column(String(20), nullable=True)  # S, M, L, XL, etc.

    # Alternativa futura: asociar por sesión anónima
    session_id = Column(String(255), nullable=True, index=True)

    product = relationship("Product")


