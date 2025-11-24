from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PaymentOut(BaseModel):
    """Schema para mostrar información financiera detallada de un pago"""
    id: int
    order_id: Optional[int]
    mp_payment_id: str
    transaction_amount: float
    currency_id: str
    payment_method_id: Optional[str]
    payment_type_id: Optional[str]
    payment_method_label: Optional[str]  # Etiqueta legible del método de pago
    card_last_four_digits: Optional[str]
    card_holder_name: Optional[str]
    status: str
    status_detail: Optional[str]
    refunded_amount: float
    refunded_count: int
    has_chargeback: str
    date_created: datetime
    date_approved: Optional[datetime]
    date_last_updated: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Información del pedido relacionado (opcional)
    order_number: Optional[str] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentListOut(BaseModel):
    """Schema simplificado para listar pagos"""
    id: int
    mp_payment_id: str
    transaction_amount: float
    currency_id: str
    payment_method_label: Optional[str]  # "Visa terminada en 4444", "Rapipago", etc.
    status: str
    date_created: datetime
    date_approved: Optional[datetime]
    refunded_amount: float
    has_chargeback: str
    order_number: Optional[str] = None
    customer_email: Optional[str] = None

    class Config:
        from_attributes = True

