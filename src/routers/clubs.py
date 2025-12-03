from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.club import Club
from ..schemas.club_schema import ClubCreate, ClubUpdate, ClubOut

router = APIRouter(prefix="/clubs", tags=["clubs"])


def _slugify(name: str) -> str:
    """
    Genera un slug sencillo a partir del nombre del club.
    """
    import re

    slug = name.lower()
    # Eliminar tildes
    slug = (
        slug.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


@router.get("/", response_model=List[ClubOut])
def list_clubs(
    city_key: Optional[str] = Query(
        default=None,
        description="Filtrar por ciudad (sanRafael, generalAlvear, malargue, sanLuis, mendoza, neuquen)",
    ),
    slug: Optional[str] = Query(
        default=None,
        description="Filtrar por slug exacto del club",
    ),
    db: Session = Depends(get_db),
):
    """
    Listado de clubes, opcionalmente filtrados por ciudad y/o slug.
    """
    query = db.query(Club)
    if city_key:
        query = query.filter(Club.city_key == city_key)
    if slug:
        query = query.filter(Club.slug == slug)
    clubs = query.order_by(Club.name.asc()).all()
    return clubs


@router.post("/", response_model=ClubOut, status_code=201)
def create_club(payload: ClubCreate, db: Session = Depends(get_db)):
    """
    Crear un nuevo club.

    - Genera automáticamente un slug único a partir del nombre.
    - city_key debe coincidir con una de las claves usadas en el frontend
      (sanRafael, generalAlvear, malargue, sanLuis, mendoza, neuquen).
    """
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="El nombre del club es obligatorio")

    if not payload.city_key.strip():
        raise HTTPException(status_code=400, detail="La ciudad del club es obligatoria")

    # Evitar duplicados por nombre
    existing_by_name = db.query(Club).filter(Club.name == payload.name.strip()).first()
    if existing_by_name:
        raise HTTPException(status_code=400, detail="Ya existe un club con ese nombre")

    base_slug = _slugify(payload.name)
    if not base_slug:
        raise HTTPException(status_code=400, detail="No se pudo generar un slug para el club")

    slug = base_slug
    counter = 1
    while db.query(Club).filter(Club.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    club = Club(
        name=payload.name.strip(),
        slug=slug,
        city_key=payload.city_key,
        crest_image_url=payload.crest_image_url,
    )

    db.add(club)
    db.commit()
    db.refresh(club)

    return club


@router.get("/{club_id}", response_model=ClubOut)
def get_club(club_id: int, db: Session = Depends(get_db)):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")
    return club


@router.put("/{club_id}", response_model=ClubOut)
def update_club(club_id: int, payload: ClubUpdate, db: Session = Depends(get_db)):
    """
    Actualizar un club existente.
    Permite cambiar nombre, ciudad y/o escudo.
    Si cambia el nombre, se recalcula el slug (asegurando unicidad).
    """
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    data = payload.model_dump(exclude_unset=True)

    # Actualizar nombre y slug si corresponde
    if "name" in data and data["name"]:
        new_name = data["name"].strip()
        if not new_name:
          raise HTTPException(status_code=400, detail="El nombre del club no puede estar vacío")

        # Evitar duplicados por nombre (excepto el mismo club)
        existing = (
            db.query(Club)
            .filter(Club.name == new_name, Club.id != club_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe otro club con ese nombre")

        club.name = new_name

        # Recalcular slug a partir del nuevo nombre
        base_slug = _slugify(new_name)
        if not base_slug:
            raise HTTPException(status_code=400, detail="No se pudo generar un slug para el club")

        slug = base_slug
        counter = 1
        while db.query(Club).filter(Club.slug == slug, Club.id != club_id).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        club.slug = slug

    # Actualizar ciudad si se envía
    if "city_key" in data and data["city_key"]:
        club.city_key = data["city_key"]

    # Actualizar escudo si se envía (puede ser None explícito para limpiar)
    if "crest_image_url" in data:
        club.crest_image_url = data["crest_image_url"]

    db.add(club)
    db.commit()
    db.refresh(club)

    return club


@router.delete("/{club_id}", status_code=204)
def delete_club(club_id: int, db: Session = Depends(get_db)):
    """
    Eliminar un club.
    No elimina productos asociados; solo remueve el registro del club.
    """
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club no encontrado")

    db.delete(club)
    db.commit()
    return None

