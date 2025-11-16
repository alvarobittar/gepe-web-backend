from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.product import Product, Category
from ..schemas.product_schema import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


def _ensure_sample_data(db: Session) -> None:
    """
    Crea algunos productos y categorías de ejemplo si la tabla está vacía.
    Esto es útil para el entorno de demo inicial.
    """
    has_products = db.query(Product).first() is not None
    if has_products:
        return

    # Crear categorías de ejemplo
    camiseta = Category(name="Camisetas", slug="camisetas")
    entrenamiento = Category(name="Entrenamiento", slug="entrenamiento")
    db.add_all([camiseta, entrenamiento])
    db.flush()

    demo_products = [
        Product(
            name="Camiseta Titular - Club GEPE",
            slug="camiseta-titular-gepe",
            description="Camiseta titular oficial del Club GEPE.",
            price=35000,
            stock=10,
            gender="hombre",
            club_name="Club GEPE",
            category=camiseta,
        ),
        Product(
            name="Camiseta Alternativa - Club GEPE",
            slug="camiseta-alternativa-gepe",
            description="Camiseta alternativa edición especial.",
            price=38000,
            stock=5,
            gender="mujer",
            club_name="Club GEPE",
            category=camiseta,
        ),
        Product(
            name="Buzo de entrenamiento GEPE",
            slug="buzo-entrenamiento-gepe",
            description="Buzo técnico para entrenamientos.",
            price=42000,
            stock=8,
            gender="unisex",
            club_name="Club GEPE",
            category=entrenamiento,
        ),
    ]
    db.add_all(demo_products)
    db.commit()


@router.get("/", response_model=List[ProductOut])
def list_products(
    q: Optional[str] = Query(default=None, description="Buscar por nombre de prenda o club"),
    gender: Optional[str] = Query(default=None, description="Filtrar por género (hombre/mujer)"),
    category: Optional[str] = Query(default=None, description="Slug de categoría"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación (número de items a saltar)"),
    limit: int = Query(20, ge=1, le=100, description="Cantidad máxima de productos a devolver"),
    db: Session = Depends(get_db),
):
    """
    Listado de productos con filtros opcionales por texto, género y categoría.
    La búsqueda por texto matchea contra nombre de producto y club_name.
    """
    _ensure_sample_data(db)

    query = db.query(Product).filter(Product.is_active.is_(True))

    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (Product.name.ilike(like))
            | (Product.club_name.ilike(like))
        )

    if gender:
        query = query.filter(Product.gender == gender)

    if category:
        query = query.join(Product.category).filter(Category.slug == category)

    products = query.order_by(Product.id.desc()).offset(offset).limit(limit).all()
    return products


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product
