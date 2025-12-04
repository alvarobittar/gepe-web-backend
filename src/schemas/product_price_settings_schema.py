from pydantic import BaseModel


class ProductPriceSettingsOut(BaseModel):
    id: int
    price_hincha: float
    price_jugador: float
    price_profesional: float

    class Config:
        from_attributes = True


class ProductPriceSettingsUpdate(BaseModel):
    price_hincha: float
    price_jugador: float
    price_profesional: float

