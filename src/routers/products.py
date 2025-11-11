from fastapi import APIRouter
from typing import List
from ..schemas.product_schema import ProductOut

router = APIRouter(prefix="/products", tags=["products"])

# Mock in-memory storage (placeholder)
_FAKE_PRODUCTS = [
    {"id": 1, "name": "Pelota", "price": 25.5},
    {"id": 2, "name": "Red", "price": 80.0},
]

@router.get("/", response_model=List[ProductOut])
async def list_products():
    return _FAKE_PRODUCTS
