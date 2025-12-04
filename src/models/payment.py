from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class Payment(Base):
    """
    Modelo para almacenar información financiera detallada de transacciones de Mercado Pago.
    Separado de Order porque un pedido puede tener múltiples intentos de pago.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con Order (opcional, porque puede haber pagos sin orden)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    
    # ID de transacción de Mercado Pago
    mp_payment_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Información financiera
    transaction_amount = Column(Float, nullable=False)  # Monto exacto
    currency_id = Column(String(10), default="ARS")  # Moneda (ARS, USD, etc.)
    
    # Método de pago
    payment_method_id = Column(String(50), nullable=True)  # visa, master, rapipago, etc.
    payment_type_id = Column(String(50), nullable=True)  # credit_card, debit_card, ticket, etc.
    card_last_four_digits = Column(String(4), nullable=True)  # Últimos 4 dígitos de tarjeta
    card_holder_name = Column(String(255), nullable=True)  # Nombre del titular
    
    # Estado del pago
    status = Column(String(50), nullable=False)  # approved, pending, rejected, cancelled, refunded, charged_back
    status_detail = Column(String(100), nullable=True)  # Detalle del estado
    
    # Información de reembolsos
    refunded_amount = Column(Float, default=0.0)  # Monto reembolsado
    refunded_count = Column(Integer, default=0)  # Cantidad de reembolsos
    
    # Información de contracargos
    has_chargeback = Column(String(10), default="false")  # true/false como string para compatibilidad
    
    # Fechas
    date_created = Column(DateTime, nullable=False)  # Fecha de creación en MP
    date_approved = Column(DateTime, nullable=True)  # Fecha de aprobación
    date_last_updated = Column(DateTime, nullable=True)  # Última actualización en MP
    
    # Timestamps locales
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Información adicional (JSON como texto para flexibilidad)
    mp_raw_data = Column(Text, nullable=True)  # Datos completos de MP en JSON
    
    # Relationships
    order = relationship("Order", foreign_keys=[order_id])




