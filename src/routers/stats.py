from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models.product import Product, Category
from ..models.promo_banner import PromoBanner

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/ranking")
async def get_ranking():
    # Placeholder ranking; would call services.ranking_service in real app
    return {
        "ranking": [
            {"product_id": 2, "score": 91},
            {"product_id": 1, "score": 75},
        ]
    }


@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Endpoint para obtener estadísticas del dashboard de administración.
    Retorna conteos de productos, categorías, mensajes promo y usuarios.
    """
    products_count = db.query(func.count(Product.id)).scalar() or 0
    categories_count = db.query(func.count(Category.id)).scalar() or 0
    promo_banners_count = db.query(func.count(PromoBanner.id)).scalar() or 0
    
    return {
        "products": products_count,
        "categories": categories_count,
        "promo_banners": promo_banners_count,
        "users": 0,  # Por ahora retornamos 0, se puede implementar después
    }
