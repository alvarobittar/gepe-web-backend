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
    price_hincha: Optional[float] = None
    price_jugador: Optional[float] = None
    price_profesional: Optional[float] = None
    preview_image_url: Optional[str] = None
    image1_url: Optional[str] = None
    image2_url: Optional[str] = None
    image3_url: Optional[str] = None
    image4_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    gender: Optional[str] = None
    club_name: Optional[str] = None
    category_id: Optional[int] = None
    slug: Optional[str] = None
    is_active: Optional[bool] = None
    price_hincha: Optional[float] = None
    price_jugador: Optional[float] = None
    price_profesional: Optional[float] = None
    preview_image_url: Optional[str] = None
    image1_url: Optional[str] = None
    image2_url: Optional[str] = None
    image3_url: Optional[str] = None
    image4_url: Optional[str] = None
    manual_sales_adjustment: Optional[int] = None


class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    slug: str
    price: float
    gender: Optional[str] = None
    club_name: Optional[str] = None
    price_hincha: Optional[float] = None
    price_jugador: Optional[float] = None
    price_profesional: Optional[float] = None
    preview_image_url: Optional[str] = None
    image1_url: Optional[str] = None
    image2_url: Optional[str] = None
    image3_url: Optional[str] = None
    image4_url: Optional[str] = None
    category: Optional[CategoryOut] = None
    size_stocks: Optional[List[ProductSizeStockOut]] = None
    is_active: bool
    manual_sales_adjustment: int = 0

    class Config:
        from_attributes = True
