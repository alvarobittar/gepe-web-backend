from sqlalchemy import Column, Integer, Float

from ..database import Base


class ProductPriceSettings(Base):
    __tablename__ = "product_price_settings"

    id = Column(Integer, primary_key=True, default=1)
    price_hincha = Column(Float, nullable=False, default=59900.0)
    price_jugador = Column(Float, nullable=False, default=69900.0)
    price_profesional = Column(Float, nullable=False, default=89900.0)

