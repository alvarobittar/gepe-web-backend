from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.cart import CartItem
from ..models.product import Product

router = APIRouter(prefix="/cart", tags=["cart"])


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1


class CartItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int

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
    result: List[CartItemOut] = []
    for item in items:
        result.append(
            CartItemOut(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name if item.product else "",
                quantity=item.quantity,
            )
        )
    return result


@router.post("/items", response_model=CartItemOut)
def add_cart_item(payload: CartItemCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    item = (
        db.query(CartItem)
        .filter(CartItem.product_id == payload.product_id)
        .first()
    )
    if item:
        item.quantity += payload.quantity
    else:
        item = CartItem(product_id=payload.product_id, quantity=payload.quantity)
        db.add(item)

    db.commit()
    db.refresh(item)

    return CartItemOut(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product.name if item.product else "",
        quantity=item.quantity,
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


