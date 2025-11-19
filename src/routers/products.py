from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.product import Product, Category, ProductSizeStock
from ..schemas.product_schema import (
    ProductOut, ProductSizeStockOut, ProductSizeStockUpdate,
    ProductCreate, ProductUpdate, CategoryOut
)

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

    # Cargar size_stocks con eager loading
    query = query.options(joinedload(Product.size_stocks))
    
    products = query.order_by(Product.id.desc()).offset(offset).limit(limit).all()
    return products


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).options(joinedload(Product.size_stocks)).filter(
        Product.id == product_id, Product.is_active.is_(True)
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.get("/{product_id}/stock", response_model=List[ProductSizeStockOut])
def get_product_stock(product_id: int, db: Session = Depends(get_db)):
    """Obtener stock por talle de un producto"""
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    stock_items = db.query(ProductSizeStock).filter(ProductSizeStock.product_id == product_id).all()
    return stock_items


@router.put("/{product_id}/stock/{size}", response_model=ProductSizeStockOut)
def update_product_stock(
    product_id: int,
    size: str,
    stock_update: ProductSizeStockUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar stock de un talle específico"""
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Buscar o crear el registro de stock para este talle
    size_stock = db.query(ProductSizeStock).filter(
        ProductSizeStock.product_id == product_id,
        ProductSizeStock.size == size
    ).first()
    
    if size_stock:
        size_stock.stock = stock_update.stock
    else:
        size_stock = ProductSizeStock(
            product_id=product_id,
            size=size,
            stock=stock_update.stock
        )
        db.add(size_stock)
    
    db.commit()
    db.refresh(size_stock)
    return size_stock


@router.get("/low-stock/list", response_model=List[ProductOut])
def get_low_stock_products(
    threshold: int = Query(3, ge=0, description="Umbral de stock bajo"),
    db: Session = Depends(get_db)
):
    """Obtener productos con stock bajo (menos de threshold unidades en cualquier talle)"""
    # Buscar productos que tengan al menos un talle con stock bajo
    low_stock_size_stocks = db.query(ProductSizeStock).filter(
        ProductSizeStock.stock < threshold
    ).all()
    
    # Obtener los IDs únicos de productos con stock bajo
    product_ids = list(set([stock.product_id for stock in low_stock_size_stocks]))
    
    if not product_ids:
        return []
    
    # Obtener los productos completos con size_stocks
    products = db.query(Product).options(joinedload(Product.size_stocks)).filter(
        Product.id.in_(product_ids),
        Product.is_active.is_(True)
    ).all()
    
    return products


@router.post("/", response_model=ProductOut)
def create_product(product_data: ProductCreate, db: Session = Depends(get_db)):
    """Crear un nuevo producto"""
    # Generar slug si no se proporciona
    if not product_data.slug:
        import re
        slug = re.sub(r'[^a-z0-9]+', '-', product_data.name.lower()).strip('-')
        # Asegurar que el slug sea único
        base_slug = slug
        counter = 1
        while db.query(Product).filter(Product.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
    else:
        # Verificar que el slug sea único
        if db.query(Product).filter(Product.slug == product_data.slug).first():
            raise HTTPException(status_code=400, detail="El slug ya existe")
        slug = product_data.slug
    
    # Verificar categoría si se proporciona
    category = None
    if product_data.category_id:
        category = db.query(Category).filter(Category.id == product_data.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    product = Product(
        name=product_data.name,
        slug=slug,
        description=product_data.description,
        price=product_data.price,
        gender=product_data.gender,
        club_name=product_data.club_name,
        category_id=product_data.category_id,
        is_active=product_data.is_active,
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Cargar relaciones
    product = db.query(Product).options(joinedload(Product.size_stocks)).filter(
        Product.id == product.id
    ).first()
    
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar un producto existente"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Actualizar campos proporcionados
    if product_data.name is not None:
        product.name = product_data.name
    if product_data.description is not None:
        product.description = product_data.description
    if product_data.price is not None:
        product.price = product_data.price
    if product_data.gender is not None:
        product.gender = product_data.gender
    if product_data.club_name is not None:
        product.club_name = product_data.club_name
    if product_data.category_id is not None:
        # Verificar que la categoría existe
        if product_data.category_id:
            category = db.query(Category).filter(Category.id == product_data.category_id).first()
            if not category:
                raise HTTPException(status_code=404, detail="Categoría no encontrada")
        product.category_id = product_data.category_id
    if product_data.slug is not None:
        # Verificar que el slug sea único (excepto para este producto)
        existing = db.query(Product).filter(
            Product.slug == product_data.slug,
            Product.id != product_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="El slug ya existe")
        product.slug = product_data.slug
    if product_data.is_active is not None:
        product.is_active = product_data.is_active
    
    db.commit()
    db.refresh(product)
    
    # Cargar relaciones
    product = db.query(Product).options(joinedload(Product.size_stocks)).filter(
        Product.id == product.id
    ).first()
    
    return product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Eliminar/desactivar un producto (soft delete)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Soft delete: marcar como inactivo
    product.is_active = False
    db.commit()
    
    return {"message": "Producto eliminado correctamente"}


@router.get("/categories/list", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """Obtener lista de todas las categorías"""
    categories = db.query(Category).order_by(Category.name).all()
    return categories
