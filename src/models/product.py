from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)

    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), index=True, nullable=False)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    description = Column(String(1000), nullable=True)

    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)

    # hombre / mujer / unisex, etc.
    gender = Column(String(20), index=True, nullable=True)

    # Nombre del club asociado (string simple por ahora)
    club_name = Column(String(200), index=True, nullable=True)

    is_active = Column(Boolean, default=True)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="products")
