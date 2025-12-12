"""
API Router para suscripciones al newsletter.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from src.database import get_db
from src.models.newsletter_subscriber import NewsletterSubscriber

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


class SubscribeRequest(BaseModel):
    email: EmailStr
    source: Optional[str] = "footer"


class SubscribeResponse(BaseModel):
    success: bool
    message: str


@router.post("/subscribe", response_model=SubscribeResponse)
def subscribe_to_newsletter(
    request: SubscribeRequest,
    db: Session = Depends(get_db)
):
    """
    Suscribir un email al newsletter.
    Si el email ya existe y está activo, devuelve mensaje amigable.
    Si existe pero está desuscrito, lo reactiva.
    """
    # Buscar si el email ya existe
    existing = db.query(NewsletterSubscriber).filter(
        NewsletterSubscriber.email == request.email.lower()
    ).first()
    
    if existing:
        if existing.is_active:
            return SubscribeResponse(
                success=True,
                message="¡Ya estás suscrito! Te mantendremos al tanto de las novedades."
            )
        else:
            # Reactivar suscripción
            existing.is_active = True
            existing.subscribed_at = datetime.utcnow()
            existing.source = request.source
            db.commit()
            return SubscribeResponse(
                success=True,
                message="¡Bienvenido de nuevo! Reactivamos tu suscripción."
            )
    
    # Crear nueva suscripción
    try:
        subscriber = NewsletterSubscriber(
            email=request.email.lower(),
            source=request.source
        )
        db.add(subscriber)
        db.commit()
        
        return SubscribeResponse(
            success=True,
            message="¡Gracias por suscribirte! Recibirás las novedades de GEPE."
        )
    except IntegrityError:
        db.rollback()
        return SubscribeResponse(
            success=True,
            message="¡Ya estás suscrito!"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al procesar la suscripción")


@router.get("/subscribers/count")
def get_subscribers_count(db: Session = Depends(get_db)):
    """
    Obtener conteo de suscriptores activos (para admin).
    """
    count = db.query(NewsletterSubscriber).filter(
        NewsletterSubscriber.is_active == True
    ).count()
    return {"count": count}
