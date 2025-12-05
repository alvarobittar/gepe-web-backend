from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models.notification_email import NotificationEmail
from ..services.email_service import send_test_email, get_email_config_info
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class NotificationEmailIn(BaseModel):
    email: EmailStr


class NotificationEmailOut(BaseModel):
    id: int
    email: str
    verified: bool
    created_at: datetime
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/notification-emails", response_model=List[NotificationEmailOut])
def get_notification_emails(db: Session = Depends(get_db)):
    """
    Obtiene la lista de todos los correos de notificación configurados.
    """
    try:
        emails = db.query(NotificationEmail).order_by(NotificationEmail.created_at.desc()).all()
        return emails
    except Exception as e:
        logger.error(f"Error al obtener correos de notificación: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener correos de notificación")


@router.post("/notification-emails", response_model=NotificationEmailOut)
async def add_notification_email(
    email_data: NotificationEmailIn,
    db: Session = Depends(get_db)
):
    """
    Agrega un nuevo correo de notificación y envía un correo de prueba automáticamente.
    """
    try:
        # Verificar si el correo ya existe
        existing_email = db.query(NotificationEmail).filter(
            NotificationEmail.email == email_data.email.lower().strip()
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="Este correo electrónico ya está registrado"
            )
        
        # Crear nuevo correo de notificación
        new_email = NotificationEmail(
            email=email_data.email.lower().strip(),
            verified=False
        )
        
        db.add(new_email)
        db.commit()
        db.refresh(new_email)
        
        # Enviar correo de prueba
        email_sent = False
        email_error = None
        try:
            email_sent = await send_test_email(new_email.email)
            if email_sent:
                new_email.verified = True
                new_email.verified_at = datetime.utcnow()
                db.commit()
                db.refresh(new_email)
                logger.info(f"✅ Correo de prueba enviado exitosamente a {new_email.email}")
            else:
                logger.warning(f"⚠️ No se pudo enviar correo de prueba a {new_email.email} - Verifica la configuración de Resend")
                email_error = "No se pudo enviar el correo de prueba. Verifica la configuración de RESEND_API_KEY."
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Error al enviar correo de prueba: {error_msg}", exc_info=True)
            email_error = f"Error al enviar correo: {error_msg}"
            # No lanzamos excepción aquí, el correo ya está guardado
        
        # Si hubo un error al enviar, lo incluimos en la respuesta pero no fallamos
        if email_error:
            logger.warning(f"Correo guardado pero no verificado: {new_email.email}. Error: {email_error}")
        
        return new_email
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al agregar correo de notificación: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al agregar correo de notificación"
        )


@router.delete("/notification-emails/{email_id}")
def delete_notification_email(email_id: int, db: Session = Depends(get_db)):
    """
    Elimina un correo de notificación por su ID.
    """
    try:
        email = db.query(NotificationEmail).filter(NotificationEmail.id == email_id).first()
        
        if not email:
            raise HTTPException(status_code=404, detail="Correo de notificación no encontrado")
        
        db.delete(email)
        db.commit()
        
        return {"message": "Correo de notificación eliminado exitosamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al eliminar correo de notificación: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al eliminar correo de notificación"
        )


@router.get("/email-config-status")
def get_email_config_status():
    """
    Verifica el estado de la configuración del servicio de email (Resend).
    """
    status = get_email_config_info()
    
    if not status["resend_available"]:
        status["error"] = "Resend no está instalado. Ejecuta: pip install resend"
    elif not status["api_key_configured"]:
        status["error"] = "RESEND_API_KEY no está configurada en las variables de entorno. Agrega esta variable en tu archivo .env"
    
    return status
