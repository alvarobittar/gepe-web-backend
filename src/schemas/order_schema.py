from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class OrderItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    product_size: Optional[str] = None
    quantity: int
    unit_price: float


class OrderItemOut(BaseModel):
    id: int
    product_id: Optional[int]
    product_name: str
    product_size: Optional[str]
    quantity: int
    unit_price: float

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    customer_email: EmailStr
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_dni: Optional[str] = None
    shipping_method: Optional[str] = None
    shipping_address: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_province: Optional[str] = None
    external_reference: Optional[str] = None
    payment_id: Optional[str] = None
    status: Optional[str] = "CART"  # Default to CART for new orders
    items: List[OrderItemCreate]



class OrderUpdate(BaseModel):
    status: Optional[str] = None  # PENDING, PAID, IN_PRODUCTION, SHIPPED, DELIVERED, CANCELLED, REFUNDED
    production_status: Optional[str] = None  # WAITING_FABRIC, CUTTING, SEWING, PRINTING, FINISHED
    payment_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_dni: Optional[str] = None
    shipping_address: Optional[str] = None

    shipping_city: Optional[str] = None
    shipping_province: Optional[str] = None
    tracking_code: Optional[str] = None
    tracking_company: Optional[str] = None  # Empresa de envío
    tracking_branch_address: Optional[str] = None  # Dirección de sucursal
    tracking_attachment_url: Optional[str] = None  # Link al comprobante/imagen



class ProductionStatusUpdate(BaseModel):
    """Schema para actualizar solo el estado de producción"""
    production_status: str  # WAITING_FABRIC, CUTTING, SEWING, PRINTING, FINISHED


class OrderOut(BaseModel):
    id: int
    order_number: Optional[str]  # Número público único (ej: GEPE-ABC123)
    user_id: Optional[int]
    status: str
    total_amount: float
    external_reference: Optional[str]
    payment_id: Optional[str]
    customer_email: Optional[str]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_dni: Optional[str]
    shipping_method: Optional[str]
    shipping_address: Optional[str]
    shipping_city: Optional[str]
    shipping_province: Optional[str]
    tracking_code: Optional[str]  # Código de seguimiento
    tracking_company: Optional[str] = None  # Empresa de envío
    tracking_branch_address: Optional[str] = None  # Dirección de sucursal
    tracking_attachment_url: Optional[str] = None  # Link a comprobante
    production_status: Optional[str]  # Estado de producción
    confirmation_email_sent: Optional[bool] = False
    shipped_email_sent: Optional[bool] = False
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut]

    class Config:
        from_attributes = True


class OrderListOut(BaseModel):
    id: int
    order_number: Optional[str]  # Número público único (ej: GEPE-ABC123)
    customer_email: Optional[str]
    customer_name: Optional[str]
    status: str
    total_amount: float
    created_at: datetime
    items_count: int = 0
    first_product_name: Optional[str] = None  # Nombre del primer producto para vista previa
    payment_id: Optional[str] = None  # ID del pago en Mercado Pago
    external_reference: Optional[str] = None  # Referencia externa de Mercado Pago
    shipping_method: Optional[str] = None  # Método de envío
    shipping_address: Optional[str] = None  # Dirección de envío
    shipping_city: Optional[str] = None  # Ciudad de envío
    shipping_province: Optional[str] = None  # Provincia de envío
    tracking_code: Optional[str] = None  # Código de seguimiento
    tracking_company: Optional[str] = None  # Empresa de envío
    tracking_branch_address: Optional[str] = None  # Dirección de sucursal
    tracking_attachment_url: Optional[str] = None  # Link a comprobante
    production_status: Optional[str] = None  # Estado de producción

    class Config:
        from_attributes = True

