from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models.cart import CartItem
from ..models.product import Product
from ..models.product_price_settings import ProductPriceSettings
from ..models.user import User

router = APIRouter(prefix="/cart", tags=["cart"])
logger = logging.getLogger(__name__)


# ============================================================================
# DEPENDENCIAS - Extracción de headers
# ============================================================================

def get_session_id(x_session_id: Optional[str] = Header(None)) -> Optional[str]:
    """
    Obtiene el session_id del header X-Session-Id.
    Retorna None si no se proporciona (para SSR/Server Components).
    """
    return x_session_id if x_session_id else None


def get_user_email(x_user_email: Optional[str] = Header(None)) -> Optional[str]:
    """
    Obtiene el email del usuario autenticado del header X-User-Email.
    Retorna None si el usuario no está logueado.
    """
    return x_user_email if x_user_email else None


def get_cart_identifier(
    session_id: Optional[str] = Depends(get_session_id),
    user_email: Optional[str] = Depends(get_user_email),
    db: Session = Depends(get_db)
) -> tuple[Optional[int], Optional[str]]:
    """
    Determina el identificador del carrito (user_id o session_id).
    Prioridad: user_id > session_id
    
    Returns:
        tuple (user_id, session_id) donde uno de los dos puede ser None
    """
    user_id = None
    
    if user_email:
        # Buscar usuario por email
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            user_id = user.id
            logger.debug(f"Usuario autenticado: {user_email} (id={user_id})")
    
    return (user_id, session_id)


def require_cart_identifier(
    session_id: Optional[str] = Depends(get_session_id),
    user_email: Optional[str] = Depends(get_user_email),
    db: Session = Depends(get_db)
) -> tuple[Optional[int], str]:
    """
    Versión estricta que requiere al menos session_id.
    Usado para operaciones de escritura.
    """
    user_id = None
    
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            user_id = user.id
    
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID requerido. Por favor recarga la página."
        )
    
    return (user_id, session_id)


# ============================================================================
# SCHEMAS
# ============================================================================

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1
    calidad: str | None = None
    talle: str | None = None


class CartItemUpdate(BaseModel):
    quantity: int


class CartItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    calidad: str | None = None
    talle: str | None = None
    preview_image_url: str | None = None
    unit_price: float = 0.0

    class Config:
        from_attributes = True


# ============================================================================
# HELPERS
# ============================================================================

def get_price_settings(db: Session) -> dict:
    """Obtiene la configuración de precios global."""
    price_settings = db.query(ProductPriceSettings).first()
    default_prices = {
        "HINCHA": 59900.0,
        "JUGADOR": 69900.0,
        "PROFESIONAL": 89900.0,
    }
    if price_settings:
        default_prices = {
            "HINCHA": price_settings.price_hincha,
            "JUGADOR": price_settings.price_jugador,
            "PROFESIONAL": price_settings.price_profesional,
        }
    return default_prices


def build_cart_query(db: Session, user_id: Optional[int], session_id: Optional[str]):
    """
    Construye la query para obtener items del carrito.
    - Si hay user_id: buscar por user_id
    - Si no hay user_id: buscar por session_id
    """
    query = db.query(CartItem).join(Product, CartItem.product_id == Product.id)
    
    if user_id:
        return query.filter(CartItem.user_id == user_id)
    elif session_id:
        return query.filter(CartItem.session_id == session_id)
    else:
        # Sin identificador, retornar query vacía
        return query.filter(CartItem.id == -1)


def cart_item_to_out(item: CartItem, default_prices: dict) -> CartItemOut:
    """Convierte un CartItem a CartItemOut con precio calculado."""
    calidad = (item.calidad or "JUGADOR").upper()
    unit_price = default_prices.get(calidad, default_prices["JUGADOR"])
    
    return CartItemOut(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product.name if item.product else "",
        quantity=item.quantity,
        calidad=item.calidad,
        talle=item.talle,
        preview_image_url=item.product.preview_image_url if item.product else None,
        unit_price=unit_price,
    )


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/items", response_model=List[CartItemOut])
def list_cart_items(
    cart_id: tuple = Depends(get_cart_identifier),
    db: Session = Depends(get_db)
):
    """Lista los items del carrito del usuario o sesión actual."""
    user_id, session_id = cart_id
    
    # Si no hay identificador (SSR), devolver vacío
    if not user_id and not session_id:
        return []
    
    items = build_cart_query(db, user_id, session_id).all()
    default_prices = get_price_settings(db)
    
    return [cart_item_to_out(item, default_prices) for item in items]


@router.post("/items", response_model=CartItemOut)
def add_cart_item(
    payload: CartItemCreate,
    cart_id: tuple = Depends(require_cart_identifier),
    db: Session = Depends(get_db)
):
    """Agrega un item al carrito."""
    user_id, session_id = cart_id
    
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Buscar item existente con las mismas características
    query = db.query(CartItem).filter(
        CartItem.product_id == payload.product_id,
        CartItem.calidad == payload.calidad,
        CartItem.talle == payload.talle,
    )
    
    if user_id:
        query = query.filter(CartItem.user_id == user_id)
    else:
        query = query.filter(CartItem.session_id == session_id)
    
    item = query.first()
    
    if item:
        item.quantity += payload.quantity
    else:
        item = CartItem(
            product_id=payload.product_id,
            quantity=payload.quantity,
            calidad=payload.calidad,
            talle=payload.talle,
            user_id=user_id,
            session_id=session_id if not user_id else None,
        )
        db.add(item)

    db.commit()
    db.refresh(item)

    default_prices = get_price_settings(db)
    return cart_item_to_out(item, default_prices)


@router.put("/items/{item_id}", response_model=CartItemOut)
def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    cart_id: tuple = Depends(require_cart_identifier),
    db: Session = Depends(get_db)
):
    """Actualiza la cantidad de un item en el carrito."""
    user_id, session_id = cart_id
    
    if payload.quantity < 1:
        raise HTTPException(status_code=400, detail="La cantidad mínima es 1")

    # Buscar item por ID y verificar que pertenece al usuario/sesión
    query = db.query(CartItem).filter(CartItem.id == item_id)
    
    if user_id:
        query = query.filter(CartItem.user_id == user_id)
    else:
        query = query.filter(CartItem.session_id == session_id)
    
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    item.quantity = payload.quantity
    db.commit()
    db.refresh(item)

    default_prices = get_price_settings(db)
    return cart_item_to_out(item, default_prices)


@router.delete("/items/{item_id}")
def delete_cart_item(
    item_id: int,
    cart_id: tuple = Depends(require_cart_identifier),
    db: Session = Depends(get_db)
):
    """Elimina un item del carrito."""
    user_id, session_id = cart_id
    
    query = db.query(CartItem).filter(CartItem.id == item_id)
    
    if user_id:
        query = query.filter(CartItem.user_id == user_id)
    else:
        query = query.filter(CartItem.session_id == session_id)
    
    item = query.first()
    if item:
        db.delete(item)
        db.commit()
    
    return {}


@router.delete("/items")
def clear_cart(
    cart_id: tuple = Depends(require_cart_identifier),
    db: Session = Depends(get_db)
):
    """Vacía el carrito del usuario/sesión actual."""
    user_id, session_id = cart_id
    
    try:
        query = db.query(CartItem)
        
        if user_id:
            query = query.filter(CartItem.user_id == user_id)
        else:
            query = query.filter(CartItem.session_id == session_id)
        
        deleted_count = query.delete()
        db.commit()
        return {"message": f"{deleted_count} items eliminados", "deleted_count": deleted_count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al vaciar carrito: {str(e)}")


@router.post("/merge")
def merge_anonymous_cart(
    cart_id: tuple = Depends(require_cart_identifier),
    db: Session = Depends(get_db)
):
    """
    Fusiona el carrito anónimo (session_id) con el carrito del usuario.
    Se llama automáticamente cuando el usuario hace login.
    
    Comportamiento:
    - Items anónimos se transfieren al user_id
    - Si ya existe un item idéntico (mismo producto, calidad, talle), se suman las cantidades
    - El session_id se limpia de los items migrados
    """
    user_id, session_id = cart_id
    
    if not user_id:
        # Usuario no autenticado, no hay nada que fusionar
        return {"message": "No hay usuario autenticado", "merged_count": 0}
    
    if not session_id:
        return {"message": "No hay session_id", "merged_count": 0}
    
    # Buscar items anónimos de este session_id
    anonymous_items = db.query(CartItem).filter(
        CartItem.session_id == session_id,
        CartItem.user_id == None
    ).all()
    
    if not anonymous_items:
        return {"message": "No hay items anónimos para fusionar", "merged_count": 0}
    
    merged_count = 0
    
    for anon_item in anonymous_items:
        # Buscar si ya existe un item idéntico en el carrito del usuario
        existing = db.query(CartItem).filter(
            CartItem.user_id == user_id,
            CartItem.product_id == anon_item.product_id,
            CartItem.calidad == anon_item.calidad,
            CartItem.talle == anon_item.talle,
        ).first()
        
        if existing:
            # Sumar cantidades
            existing.quantity += anon_item.quantity
            db.delete(anon_item)
        else:
            # Transferir al usuario
            anon_item.user_id = user_id
            anon_item.session_id = None
        
        merged_count += 1
    
    db.commit()
    logger.info(f"Fusionados {merged_count} items del carrito anónimo al usuario {user_id}")
    
    return {"message": f"{merged_count} items fusionados", "merged_count": merged_count}
