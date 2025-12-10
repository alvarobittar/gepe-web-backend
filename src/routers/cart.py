from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.cart import CartItem
from ..models.product import Product
from ..models.product_price_settings import ProductPriceSettings

router = APIRouter(prefix="/cart", tags=["cart"])


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


@router.get("/items", response_model=List[CartItemOut])
def list_cart_items(db: Session = Depends(get_db)):
    # MVP: usamos un usuario invitado único (id=1)
    items = (
        db.query(CartItem)
        .join(Product, CartItem.product_id == Product.id)
        .all()
    )
    
    # Obtener configuración de precios global
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
    
    result: List[CartItemOut] = []
    for item in items:
        # Calcular precio según calidad
        calidad = (item.calidad or "JUGADOR").upper()
        unit_price = default_prices.get(calidad, default_prices["JUGADOR"])
        
        result.append(
            CartItemOut(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name if item.product else "",
                quantity=item.quantity,
                calidad=item.calidad,
                talle=item.talle,
                preview_image_url=item.product.preview_image_url if item.product else None,
                unit_price=unit_price,
            )
        )
    return result


@router.post("/items", response_model=CartItemOut)
def add_cart_item(payload: CartItemCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Buscar item existente con mismo product_id, calidad y talle
    item = (
        db.query(CartItem)
        .filter(
            CartItem.product_id == payload.product_id,
            CartItem.calidad == payload.calidad,
            CartItem.talle == payload.talle
        )
        .first()
    )
    if item:
        item.quantity += payload.quantity
    else:
        item = CartItem(
            product_id=payload.product_id,
            quantity=payload.quantity,
            calidad=payload.calidad,
            talle=payload.talle
        )
        db.add(item)

    db.commit()
    db.refresh(item)

    # Calcular precio según calidad
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


@router.put("/items/{item_id}", response_model=CartItemOut)
def update_cart_item(item_id: int, payload: CartItemUpdate, db: Session = Depends(get_db)):
    if payload.quantity < 1:
        raise HTTPException(status_code=400, detail="La cantidad mínima es 1")

    item = db.query(CartItem).filter(CartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    item.quantity = payload.quantity
    db.add(item)
    db.commit()
    db.refresh(item)

    # Calcular precio según calidad
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


@router.delete("/items/{item_id}", response_model=None)
def delete_cart_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(CartItem).filter(CartItem.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    return {}


@router.delete("/items", response_model=None)
def clear_cart(db: Session = Depends(get_db)):
    """
    Elimina todos los items del carrito del usuario actual.
    Útil para vaciar el carrito después de completar una compra.
    """
    try:
        # MVP: eliminar todos los items del carrito (usuario invitado único)
        deleted_count = db.query(CartItem).delete()
        db.commit()
        return {"message": f"{deleted_count} items eliminados del carrito", "deleted_count": deleted_count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al vaciar carrito: {str(e)}")


