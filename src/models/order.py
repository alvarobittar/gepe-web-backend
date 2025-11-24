from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(20), unique=True, nullable=True, index=True)  # Número público único (ej: GEPE-ABC123)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(50), default="PENDING")  # PENDING, PAID, CANCELLED, REFUNDED
    total_amount = Column(Float, default=0.0)
    external_reference = Column(String(100), nullable=True, index=True)  # Referencia de Mercado Pago
    payment_id = Column(String(100), nullable=True, index=True)  # ID del pago en Mercado Pago
    
    # Datos del cliente
    customer_email = Column(String(255), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    customer_dni = Column(String(50), nullable=True)
    
    # Datos de envío
    shipping_method = Column(String(50), nullable=True)  # domicilio, retiro
    shipping_address = Column(String(500), nullable=True)
    shipping_city = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user = relationship("User", foreign_keys=[user_id])


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, nullable=True)  # Puede ser NULL si el producto se elimina después
    product_name = Column(String(255), nullable=False)
    product_size = Column(String(50), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    
    # Relationship
    order = relationship("Order", back_populates="items")


