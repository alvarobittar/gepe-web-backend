import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.notification_email import NotificationEmail
from ..services.email_service import send_regret_notification_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/returns", tags=["returns"])


class RegretRequest(BaseModel):
    nombre: str
    apellido: str
    dni: str
    ciudad: str
    numeroPedido: str
    articulosComprados: str
    telefono: str
    correo: EmailStr
    motivo: str


@router.post("/regret", status_code=status.HTTP_200_OK)
async def create_regret_request(payload: RegretRequest, db: Session = Depends(get_db)):
    """
    Recibe solicitudes de arrepentimiento de compra y envía notificación por email
    a los correos configurados en NotificationEmail.
    """
    try:
        admin_emails = [item.email for item in db.query(NotificationEmail).all()]
        if not admin_emails:
            logger.warning("No hay emails configurados para notificaciones de arrepentimiento")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No hay emails configurados para notificaciones")

        ok = await send_regret_notification_email(payload.dict(), admin_emails)
        if not ok:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo enviar el email de notificación")

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando arrepentimiento de compra: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno")

