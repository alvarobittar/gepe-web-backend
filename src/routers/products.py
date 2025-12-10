from typing import List, Optional
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.product import Product, Category, ProductSizeStock
from ..models.product_price_settings import ProductPriceSettings
from ..schemas.product_schema import (
    ProductOut, ProductSizeStockOut, ProductSizeStockUpdate,
    ProductCreate, ProductUpdate, CategoryOut
)
from ..schemas.product_price_settings_schema import (
    ProductPriceSettingsOut, ProductPriceSettingsUpdate
)
from ..utils import slugify
from ..services.revalidation_service import revalidate_product, revalidate_prices

router = APIRouter(prefix="/products", tags=["products"])


def _trigger_revalidation(slug: str | None = None):
    """Helper para disparar revalidación en background."""
    try:
        asyncio.create_task(revalidate_product(slug))
    except RuntimeError:
        # Si no hay event loop, crear uno temporalmente
        loop = asyncio.new_event_loop()
        loop.run_until_complete(revalidate_product(slug))
        loop.close()




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


def _list_products_impl(
    q: Optional[str] = None,
    gender: Optional[str] = None,
    category: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
    db: Session = None,
    include_inactive: bool = False,
):
    """
    Implementación compartida para listar productos.
    """
    _ensure_sample_data(db)

    query = db.query(Product)
    # Solo filtrar por is_active si no se incluyen inactivos (para admin)
    if not include_inactive:
        query = query.filter(Product.is_active.is_(True))

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


@router.get("", response_model=List[ProductOut])
def list_products_no_slash(
    q: Optional[str] = Query(default=None, description="Buscar por nombre de prenda o club"),
    gender: Optional[str] = Query(default=None, description="Filtrar por género (hombre/mujer)"),
    category: Optional[str] = Query(default=None, description="Slug de categoría"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación (número de items a saltar)"),
    limit: int = Query(20, ge=1, le=100, description="Cantidad máxima de productos a devolver"),
    include_inactive: bool = Query(default=False, description="Incluir productos inactivos (para admin)"),
    db: Session = Depends(get_db),
):
    """
    Listado de productos con filtros opcionales por texto, género y categoría.
    La búsqueda por texto matchea contra nombre de producto y club_name.
    Por defecto solo muestra productos activos. Use include_inactive=true para ver todos.
    """
    return _list_products_impl(q, gender, category, offset, limit, db, include_inactive)


@router.get("/", response_model=List[ProductOut])
def list_products(
    q: Optional[str] = Query(default=None, description="Buscar por nombre de prenda o club"),
    gender: Optional[str] = Query(default=None, description="Filtrar por género (hombre/mujer)"),
    category: Optional[str] = Query(default=None, description="Slug de categoría"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación (número de items a saltar)"),
    limit: int = Query(20, ge=1, le=100, description="Cantidad máxima de productos a devolver"),
    include_inactive: bool = Query(default=False, description="Incluir productos inactivos (para admin)"),
    db: Session = Depends(get_db),
):
    """
    Listado de productos con filtros opcionales por texto, género y categoría.
    La búsqueda por texto matchea contra nombre de producto y club_name.
    Por defecto solo muestra productos activos. Use include_inactive=true para ver todos.
    """
    return _list_products_impl(q, gender, category, offset, limit, db, include_inactive)


@router.get("/price-settings", response_model=ProductPriceSettingsOut)
def get_price_settings(db: Session = Depends(get_db)):
    """Obtener los precios globales de camisetas"""
    settings = db.query(ProductPriceSettings).filter(ProductPriceSettings.id == 1).first()
    
    if not settings:
        # Crear valores por defecto si no existen
        settings = ProductPriceSettings(
            id=1,
            price_hincha=59900.0,
            price_jugador=69900.0,
            price_profesional=89900.0
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings


@router.put("/price-settings", response_model=ProductPriceSettingsOut)
def update_price_settings(
    settings_data: ProductPriceSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar los precios globales de camisetas"""
    settings = db.query(ProductPriceSettings).filter(ProductPriceSettings.id == 1).first()
    
    if not settings:
        settings = ProductPriceSettings(id=1)
        db.add(settings)
    
    settings.price_hincha = settings_data.price_hincha
    settings.price_jugador = settings_data.price_jugador
    settings.price_profesional = settings_data.price_profesional
    
    db.commit()
    db.refresh(settings)
    
    # Revalidar cache del frontend (precios cambiaron)
    try:
        asyncio.create_task(revalidate_prices())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(revalidate_prices())
        loop.close()
    
    return settings


@router.get("/by-slug/{slug}", response_model=ProductOut)
def get_product_by_slug(slug: str, db: Session = Depends(get_db)):
    """Obtener un producto por su slug"""
    product = db.query(Product).options(joinedload(Product.size_stocks)).filter(
        Product.slug == slug, Product.is_active.is_(True)
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.get("/{product_id:int}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Obtener un producto por su ID"""
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
    # Generar slug automáticamente desde el nombre (siempre, ignorando el que venga en product_data)
    slug = slugify(product_data.name)
    # Asegurar que el slug sea único
    base_slug = slug
    counter = 1
    while db.query(Product).filter(Product.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Verificar categoría si se proporciona
    category = None
    if product_data.category_id:
        category = db.query(Category).filter(Category.id == product_data.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    # Determinar precios por calidad
    price_hincha = product_data.price_hincha if product_data.price_hincha is not None else product_data.price
    price_jugador = product_data.price_jugador
    price_profesional = product_data.price_profesional

    # El campo price base lo usamos como precio "hincha" para compatibilidad
    base_price = price_hincha or product_data.price

    product = Product(
        name=product_data.name,
        slug=slug,
        description=product_data.description,
        price=base_price,
        gender=product_data.gender,
        club_name=product_data.club_name,
        category_id=product_data.category_id,
        is_active=product_data.is_active,
        price_hincha=price_hincha,
        price_jugador=price_jugador,
        price_profesional=price_profesional,
        preview_image_url=product_data.preview_image_url,
        image1_url=product_data.image1_url,
        image2_url=product_data.image2_url,
        image3_url=product_data.image3_url,
        image4_url=product_data.image4_url,
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Cargar relaciones
    product = db.query(Product).options(joinedload(Product.size_stocks)).filter(
        Product.id == product.id
    ).first()
    
    # Revalidar cache del frontend
    _trigger_revalidation(product.slug)
    
    return product


@router.post("", response_model=ProductOut)
def create_product_no_slash(product_data: ProductCreate, db: Session = Depends(get_db)):
    """
    Crear un nuevo producto (sin slash final).
    Endpoint alternativo para evitar 405 cuando redirect_slashes está deshabilitado.
    """
    return create_product(product_data, db)


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
    
    # Obtener dict con solo los campos enviados (exclude_unset=True)
    update_data = product_data.dict(exclude_unset=True)

    # 1. Validar categoría si se está actualizando
    if "category_id" in update_data and update_data["category_id"] is not None:
        category = db.query(Category).filter(Category.id == update_data["category_id"]).first()
        if not category:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")

    # 2. Manejo especial de cambio de nombre -> Slug
    if "name" in update_data and update_data["name"] != product.name:
        new_name = update_data["name"]
        new_slug = slugify(new_name)
        # Asegurar que el slug sea único (excepto para este producto)
        base_slug = new_slug
        counter = 1
        while db.query(Product).filter(Product.slug == new_slug, Product.id != product_id).first():
            new_slug = f"{base_slug}-{counter}"
            counter += 1
        update_data["slug"] = new_slug
    
    # 3. Manejo especial de precio hincha -> precio base
    if "price_hincha" in update_data and update_data["price_hincha"] is not None:
        update_data["price"] = update_data["price_hincha"]

    # 4. Eliminar imágenes antiguas de Cloudinary si cambian
    try:
        from ..services.cloudinary_service import delete_image_from_url
        image_fields = ["preview_image_url", "image1_url", "image2_url", "image3_url", "image4_url"]
        
        for field in image_fields:
            if field in update_data:
                new_url = update_data[field]
                old_url = getattr(product, field)
                # Si hay una URL antigua y es diferente a la nueva (y no es None), borrarla
                # Nota: Si new_url es None, también borramos la antigua
                if old_url and old_url != new_url:
                    # No bloqueamos el flujo si falla el borrado, solo logueamos (idealmente)
                    # Aquí lo hacemos simple
                    delete_image_from_url(old_url)
    except Exception as e:
        print(f"Error borrando imagen antigua de Cloudinary: {e}")

    # 5. Aplicar cambios genéricos
    for field, value in update_data.items():
        # Verificar que el modelo tenga este campo antes de setearlo
        if hasattr(product, field):
            setattr(product, field, value)
    
    db.commit()
    db.refresh(product)
    
    # Cargar relaciones
    product = db.query(Product).options(joinedload(Product.size_stocks)).filter(
        Product.id == product.id
    ).first()
    
    # Revalidar cache del frontend
    _trigger_revalidation(product.slug)
    
    return product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """
    Eliminar físicamente un producto.
    Solo se puede eliminar si el producto está inactivo.
    """
    from ..models.cart import CartItem
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Solo se puede eliminar si está inactivo
    if product.is_active:
        raise HTTPException(
            status_code=400, 
            detail="No se puede eliminar un producto activo. Primero debes desactivarlo."
        )
    
    # Eliminar primero los items del carrito asociados
    cart_items = db.query(CartItem).filter(CartItem.product_id == product_id).all()
    for cart_item in cart_items:
        db.delete(cart_item)
    
    # Eliminar imágenes de Cloudinary
    try:
        from ..services.cloudinary_service import delete_image_from_url
        image_fields = ["preview_image_url", "image1_url", "image2_url", "image3_url", "image4_url"]
        for field in image_fields:
            url = getattr(product, field)
            if url:
                delete_image_from_url(url)
    except Exception as e:
        print(f"Error borrando imágenes de Cloudinary al eliminar producto: {e}")
    
    # Hard delete: eliminar físicamente el producto
    slug = product.slug  # Guardar antes de borrar
    db.delete(product)
    db.commit()
    
    # Revalidar cache del frontend
    _trigger_revalidation(slug)
    
    return {"message": "Producto eliminado correctamente"}


@router.get("/categories/list", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """Obtener lista de todas las categorías"""
    categories = db.query(Category).order_by(Category.name).all()
    return categories


@router.post("/upload-image")
async def upload_product_image(file: UploadFile = File(...)):
    """
    Subir una imagen de producto a Cloudinary.
    
    Devuelve la URL pública de la imagen subida.
    Límite máximo: 10MB
    """
    from ..services.cloudinary_service import upload_product_image as upload_fn
    
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    
    # Validar tamaño del archivo (10MB máximo)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    file_size = 0
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo es demasiado grande. Tamaño máximo: 10MB. Tamaño actual: {file_size / (1024 * 1024):.2f}MB"
        )
    
    # Resetear el archivo para poder leerlo de nuevo
    await file.seek(0)
    
    try:
        result = await upload_fn(file)
        return {"url": result["url"], "public_id": result.get("public_id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir la imagen: {str(e)}")


@router.delete("/delete-image")
async def delete_product_image(url: str = Query(..., description="URL de la imagen en Cloudinary")):
    """
    Eliminar una imagen de Cloudinary.
    
    Extrae el public_id de la URL y elimina la imagen.
    """
    from ..services.cloudinary_service import delete_image_from_url
    
    try:
        success = delete_image_from_url(url)
        if not success:
            raise HTTPException(status_code=404, detail="No se pudo eliminar la imagen")
        return {"message": "Imagen eliminada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la imagen: {str(e)}")
