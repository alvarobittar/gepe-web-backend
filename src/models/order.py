from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(50), default="pending")
    total_amount = Column(Float, default=0.0)

    # Para simplificar, no modelamos OrderItem todavía.


