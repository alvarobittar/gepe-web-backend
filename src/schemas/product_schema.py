from pydantic import BaseModel
from typing import Optional


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    gender: Optional[str] = None
    club_name: Optional[str] = None
    category: Optional[CategoryOut] = None

    class Config:
        from_attributes = True
