from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List


class ItemInput(BaseModel):
    """Schema para items de una orden"""
    id: str = Field(..., description="ID del producto")
    title: str = Field(..., description="Título del producto")
    description: Optional[str] = Field(None, description="Descripción del producto")
    picture_url: Optional[str] = Field(None, description="URL de la imagen del producto")
    category_id: Optional[str] = Field(None, description="Categoría del producto")
    quantity: int = Field(..., gt=0, description="Cantidad de items")
    unit_price: float = Field(..., gt=0, description="Precio unitario")
    currency_id: str = Field(default="ARS", description="Moneda")


class PayerIdentification(BaseModel):
    """Schema para identificación del pagador"""
    type: str = Field(..., description="Tipo de documento (DNI, CUIT, etc)")
    number: str = Field(..., description="Número de documento")


class PayerInput(BaseModel):
    """Schema para información del pagador"""
    email: EmailStr = Field(..., description="Email del pagador")
    first_name: Optional[str] = Field(None, description="Nombre del pagador")
    last_name: Optional[str] = Field(None, description="Apellido del pagador")
    identification: Optional[PayerIdentification] = Field(None, description="Identificación del pagador")


class PreferenceInput(BaseModel):
    """Schema para crear una preferencia de pago en Mercado Pago"""
    items: List[ItemInput] = Field(..., min_items=1, description="Lista de items a pagar")
    payer: PayerInput = Field(..., description="Información del pagador")
    external_reference: Optional[str] = Field(None, description="Referencia externa para identificar la orden")
    notification_url: Optional[str] = Field(None, description="URL para recibir notificaciones de webhook")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "1",
                        "title": "Camiseta River Plate 2024",
                        "description": "Camiseta oficial River Plate",
                        "quantity": 1,
                        "unit_price": 15000.0,
                        "currency_id": "ARS"
                    }
                ],
                "payer": {
                    "email": "cliente@example.com",
                    "first_name": "Juan",
                    "last_name": "Pérez",
                    "identification": {
                        "type": "DNI",
                        "number": "12345678"
                    }
                },
                "external_reference": "ORDER-12345"
            }
        }


class PreferenceResponse(BaseModel):
    """Schema para la respuesta de creación de preferencia"""
    init_point: str = Field(..., description="URL de pago de Mercado Pago")
    preference_id: str = Field(..., description="ID de la preferencia creada")
    sandbox_init_point: Optional[str] = Field(None, description="URL de pago en modo sandbox")


class WebhookNotification(BaseModel):
    """Schema para las notificaciones de webhook de Mercado Pago"""
    id: Optional[str] = Field(None, description="ID de la notificación")
    live_mode: Optional[bool] = Field(None, description="Indica si es producción o sandbox")
    type: Optional[str] = Field(None, description="Tipo de notificación (payment, merchant_order, etc)")
    date_created: Optional[str] = Field(None, description="Fecha de creación de la notificación")
    user_id: Optional[str] = Field(None, description="ID del usuario")
    api_version: Optional[str] = Field(None, description="Versión de la API")
    action: Optional[str] = Field(None, description="Acción realizada (created, updated, etc)")
    data: Optional[dict] = Field(None, description="Datos de la notificación")

