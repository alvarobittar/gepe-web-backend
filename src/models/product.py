from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, UniqueConstraint
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
    size_stocks = relationship("ProductSizeStock", back_populates="product", cascade="all, delete-orphan")


class ProductSizeStock(Base):
    __tablename__ = "product_size_stocks"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    size = Column(String(20), nullable=False)
    stock = Column(Integer, default=0, nullable=False)

    product = relationship("Product", back_populates="size_stocks")

    __table_args__ = (
        UniqueConstraint('product_id', 'size', name='unique_product_size'),
    )
