from pydantic import BaseModel
from typing import Optional, List


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True


class ProductSizeStockOut(BaseModel):
    id: int
    product_id: int
    size: str
    stock: int

    class Config:
        from_attributes = True


class ProductSizeStockUpdate(BaseModel):
    stock: int


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    gender: Optional[str] = None
    club_name: Optional[str] = None
    category_id: Optional[int] = None
    slug: Optional[str] = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    gender: Optional[str] = None
    club_name: Optional[str] = None
    category_id: Optional[int] = None
    slug: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    slug: str
    price: float
    gender: Optional[str] = None
    club_name: Optional[str] = None
    category: Optional[CategoryOut] = None
    size_stocks: Optional[List[ProductSizeStockOut]] = None
    is_active: bool

    class Config:
        from_attributes = True
