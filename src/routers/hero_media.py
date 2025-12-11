from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db, engine
from ..models.hero_media import HeroMedia
from ..schemas.hero_media_schema import (
    HeroMediaCreate,
    HeroMediaOut,
    HeroMediaUpdate,
)
from ..services.cloudinary_service import upload_image, upload_video


router = APIRouter(prefix="/hero-media", tags=["hero-media"])


def _reset_hero_media_sequence(db: Session) -> None:
    """
    Resetea la secuencia de PostgreSQL para hero_media.id
    para que apunte al siguiente ID disponible.
    Se ignora silenciosamente en SQLite.
    """
    try:
        if engine.url.drivername == "postgresql":
            db.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('hero_media', 'id'), "
                    "(SELECT COALESCE(MAX(id), 0) + 1 FROM hero_media), false)"
                )
            )
            db.commit()
    except Exception:
        try:
            db.execute(
                text(
                    "SELECT setval('hero_media_id_seq', "
                    "(SELECT COALESCE(MAX(id), 0) + 1 FROM hero_media), false)"
                )
            )
            db.commit()
        except Exception:
            pass


def _ensure_default_hero_media(db: Session) -> None:
    """
    Crea slides de ejemplo si la tabla está vacía para evitar
    que el hero quede sin contenido en instalaciones nuevas.
    """
    has_any = db.query(HeroMedia).first() is not None
    if has_any:
        return

    defaults = [
        HeroMedia(
            title="NO ES SOLO UNA CAMISETA",
            subtitle="ES LA NUESTRA",
            highlight="CAMISETA",
            image_url="/hero-banner-hd.jpg",
            display_order=0,
            is_active=True,
        ),
        HeroMedia(
            title="NO LAS VENDEMOS, LAS VIVIMOS",
            subtitle="SOMOS PARTE DEL EQUIPO",
            highlight="VIVIMOS",
            image_url="/hero-banner-hd.jpg",
            video_url="https://phosphor.utils.elfsightcdn.com/?url=https%3A%2F%2Fscontent-vie1-1.cdninstagram.com%2Fo1%2Fv%2Ft2%2Ff2%2Fm86%2FAQO_BsxEcyHfGkXIqikIJ3Z3oBYUFPPDHpvFd6Dcv2cJVjzS0_LbdYWnXEJW3t7S1rO6fp1oWDHL0WVNu8cy7yK3DuL5lQrqKghye3Q.mp4%3F_nc_cat%3D108%26_nc_sid%3D5e9851%26_nc_ht%3Dscontent-vie1-1.cdninstagram.com%26_nc_ohc%3DxvArGNHEjbUQ7kNvwEm-myL%26efg%3DeyJ2ZW5jb2RlX3RhZyI6Inhwdl9wcm9ncmVzc2l2ZS5JTlNUQUdSQU0uQ0xJUFMuQzMuNzIwLmRhc2hfYmFzZWxpbmVfMV92MSIsInhwdl9hc3NldF9pZCI6MTkwMTI4ODM2NzQ2MjMwNywiYXNzZXRfYWdlX2RheXMiOjAsInZpX3VzZWNhc2VfaWQiOjEwMDk5LCJkdXJhdGlvbl9zIjoxOSwidXJsZ2VuX3NvdXJjZSI6Ind3dyJ9%26ccb%3D17-1%26vs%3D7c5fa4cfb01b5afa%26_nc_vs%3DHBksFQIYUmlnX3hwdl9yZWVsc19wZXJtYW5lbnRfc3JfcHJvZC8zRTQyMjA2M0NGRTMyODE1OUUyMTZENUI3NDQ3MzNBRl92aWRlb19kYXNoaW5pdC5tcDQVAALIARIAFQIYOnBhc3N0aHJvdWdoX2V2ZXJzdG9yZS9HTmIzcXlKWTRrS2NnTEFGQUVsazNkT2YxWFIxYnN0VEFRQUYVAgLIARIAKAAYABsCiAd1c2Vfb2lsATEScHJvZ3Jlc3NpdmVfcmVjaXBlATEVAAAmxt6QnMbN4AYVAigCQzMsF0AzKn752yLRGBJkYXNoX2Jhc2VsaW5lXzFfdjERAHX-B2XmnQEA%26_nc_gid%3DJYOeBzj3Omf9F5tXLS4E2Q%26_nc_zt%3D28%26oh%3D00_AfjsWyMlEL0bGsSTz5Se5EcdL-8HgpFnkT4C39TG3bPLsg%26oe%3D691B1805",
            display_order=1,
            is_active=True,
        ),
    ]
    db.add_all(defaults)
    db.commit()
    _reset_hero_media_sequence(db)


def _list_active_hero_media(db: Session) -> List[HeroMedia]:
    """
    Retorna los slides activos ordenados.
    """
    _ensure_default_hero_media(db)
    return (
        db.query(HeroMedia)
        .filter(HeroMedia.is_active.is_(True))
        .order_by(HeroMedia.display_order.asc(), HeroMedia.id.asc())
        .all()
    )


@router.get("", response_model=List[HeroMediaOut])
def list_active_hero_media_no_slash(db: Session = Depends(get_db)):
    """
    Endpoint público para obtener los slides activos del hero.
    """
    return _list_active_hero_media(db)


@router.get("/", response_model=List[HeroMediaOut])
def list_active_hero_media(db: Session = Depends(get_db)):
    """
    Endpoint público para obtener los slides activos del hero.
    """
    return _list_active_hero_media(db)


@router.get("/admin", response_model=List[HeroMediaOut])
def list_hero_media_admin(db: Session = Depends(get_db)):
    """
    Endpoint de administración para listar todos los slides,
    activos e inactivos.
    """
    _ensure_default_hero_media(db)
    return (
        db.query(HeroMedia)
        .order_by(HeroMedia.display_order.asc(), HeroMedia.id.asc())
        .all()
    )


@router.post("/admin", response_model=HeroMediaOut, status_code=201)
def create_hero_media(payload: HeroMediaCreate, db: Session = Depends(get_db)):
    # Only image_url is required now, title is optional
    if not payload.image_url:
        raise HTTPException(status_code=400, detail="image_url es requerido")

    _reset_hero_media_sequence(db)
    hero = HeroMedia(
        title=payload.title or "",  # Empty string if None (SQLite constraint)
        subtitle=payload.subtitle,
        highlight=payload.highlight,
        image_url=payload.image_url,
        video_url=payload.video_url,
        image_focus_x=payload.image_focus_x,
        image_focus_y=payload.image_focus_y,
        image_zoom=payload.image_zoom,
        is_active=payload.is_active,
        display_order=payload.display_order,
        show_overlay=payload.show_overlay,
        aspect_ratio_desktop=payload.aspect_ratio_desktop,
        aspect_ratio_mobile=payload.aspect_ratio_mobile,
        link_url=payload.link_url,
    )
    db.add(hero)
    db.commit()
    db.refresh(hero)
    return hero


@router.put("/admin/{hero_id}", response_model=HeroMediaOut)
def update_hero_media(
    hero_id: int, payload: HeroMediaUpdate, db: Session = Depends(get_db)
):
    hero = db.query(HeroMedia).filter(HeroMedia.id == hero_id).first()
    if not hero:
        raise HTTPException(status_code=404, detail="HeroMedia no encontrado")

    data = payload.model_dump(exclude_unset=True)
    # Fields that can be set to empty string (for SQLite NOT NULL compatibility)
    nullable_fields = {"title", "subtitle", "highlight", "video_url", "link_url"}
    
    for key, value in data.items():
        if key in nullable_fields:
            # Convert None to empty string for title (SQLite constraint)
            if key == "title" and value is None:
                value = ""
            setattr(hero, key, value)
        elif value is not None:
            setattr(hero, key, value)

    db.add(hero)
    db.commit()
    db.refresh(hero)
    return hero


@router.delete("/admin/{hero_id}", status_code=204)
def delete_hero_media(hero_id: int, db: Session = Depends(get_db)):
    hero = db.query(HeroMedia).filter(HeroMedia.id == hero_id).first()
    if not hero:
        raise HTTPException(status_code=404, detail="HeroMedia no encontrado")

    db.delete(hero)
    db.commit()
    return None


@router.post("/admin/upload")
async def upload_hero_media(file: UploadFile = File(...)):
    """
    Upload an image or video for hero media to Cloudinary.
    Returns the URL of the uploaded asset.
    """
    if not file.content_type:
        raise HTTPException(status_code=400, detail="Tipo de archivo no válido")

    is_image = file.content_type.startswith("image/")
    is_video = file.content_type.startswith("video/")

    if not (is_image or is_video):
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser una imagen o video",
        )

    try:
        if is_video:
            result = await upload_video(file, folder="gepe/hero")
        else:
            result = await upload_image(file, folder="gepe/hero")
        return {"url": result["url"], "public_id": result["public_id"], "type": "video" if is_video else "image"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir archivo: {str(e)}"
        )
