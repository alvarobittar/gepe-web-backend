from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db, engine
from ..models.promo_banner import PromoBanner
from ..schemas.promo_banner_schema import (
    PromoBannerOut,
    PromoBannerCreate,
    PromoBannerUpdate,
)


router = APIRouter(prefix="/promo-banners", tags=["promo-banners"])


def _reset_promo_banner_sequence(db: Session) -> None:
    """
    Resetea la secuencia de PostgreSQL para promo_banners.id
    para que apunte al siguiente ID disponible.
    Solo funciona con PostgreSQL, se ignora silenciosamente en SQLite.
    """
    try:
        if engine.url.drivername == "postgresql":
            result = db.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('promo_banners', 'id'), "
                    "(SELECT COALESCE(MAX(id), 0) + 1 FROM promo_banners), false)"
                )
            )
            db.commit()
    except Exception:
        try:
            db.execute(
                text(
                    "SELECT setval('promo_banners_id_seq', "
                    "(SELECT COALESCE(MAX(id), 0) + 1 FROM promo_banners), false)"
                )
            )
            db.commit()
        except Exception:
            pass


def _ensure_default_banners(db: Session) -> None:
    """
    Crea algunos mensajes de ejemplo si la tabla está vacía.
    Solo para entorno de demo/desarrollo.
    """
    has_any = db.query(PromoBanner).first() is not None
    if has_any:
        return

    defaults = [
        PromoBanner(
            message="🚚 Envíos gratis a partir de $100.000",
            display_order=0,
            is_active=True,
        ),
        PromoBanner(
            message="💳 3 cuotas sin interés",
            display_order=1,
            is_active=True,
        ),
        PromoBanner(
            message="🏦 Recibimos solo Transferencia por ahora",
            display_order=2,
            is_active=True,
        ),
    ]
    db.add_all(defaults)
    db.commit()
    
    _reset_promo_banner_sequence(db)


def _list_active_promo_banners_impl(db: Session):
    """
    Implementación compartida para listar banners activos.
    """
    _ensure_default_banners(db)
    banners = (
        db.query(PromoBanner)
        .filter(PromoBanner.is_active.is_(True))
        .order_by(PromoBanner.display_order.asc(), PromoBanner.id.asc())
        .all()
    )
    return banners


@router.get("", response_model=List[PromoBannerOut])
def list_active_promo_banners_no_slash(db: Session = Depends(get_db)):
    """
    Endpoint público para obtener los mensajes activos del TopPromoBar,
    ordenados por display_order e id.
    """
    return _list_active_promo_banners_impl(db)


@router.get("/", response_model=List[PromoBannerOut])
def list_active_promo_banners(db: Session = Depends(get_db)):
    """
    Endpoint público para obtener los mensajes activos del TopPromoBar,
    ordenados por display_order e id.
    """
    return _list_active_promo_banners_impl(db)


@router.get("/admin", response_model=List[PromoBannerOut])
def list_all_promo_banners_admin(db: Session = Depends(get_db)):
    """
    Endpoint de administración para listar todos los mensajes,
    activos e inactivos.
    IMPORTANTE: En esta primera versión no se valida el rol admin
    desde el backend. Se asume que solo el panel admin del frontend
    llama a estos endpoints.
    """
    _ensure_default_banners(db)
    banners = (
        db.query(PromoBanner)
        .order_by(PromoBanner.display_order.asc(), PromoBanner.id.asc())
        .all()
    )
    return banners


@router.post("/admin", response_model=PromoBannerOut, status_code=201)
def create_promo_banner(payload: PromoBannerCreate, db: Session = Depends(get_db)):
    _reset_promo_banner_sequence(db)
    banner = PromoBanner(
        message=payload.message,
        is_active=payload.is_active,
        display_order=payload.display_order,
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return banner


@router.put("/admin/{banner_id}", response_model=PromoBannerOut)
def update_promo_banner(
    banner_id: int, payload: PromoBannerUpdate, db: Session = Depends(get_db)
):
    banner = db.query(PromoBanner).filter(PromoBanner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=404, detail="PromoBanner no encontrado")

    # Actualizar solo los campos que se enviaron (no None)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(banner, key, value)

    # updated_at se actualiza automáticamente por SQLAlchemy con onupdate=func.now()
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return banner


@router.delete("/admin/{banner_id}", status_code=204)
def delete_promo_banner(banner_id: int, db: Session = Depends(get_db)):
    banner = db.query(PromoBanner).filter(PromoBanner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=404, detail="PromoBanner no encontrado")

    db.delete(banner)
    db.commit()
    return None


