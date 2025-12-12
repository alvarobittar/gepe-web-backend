import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.notification_email import NotificationEmail
from ..services.email_service import send_contact_email

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactForm(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    mensaje: str = Field(..., min_length=1, max_length=2000)


@router.post("")
async def submit_contact(form: ContactForm, db: Session = Depends(get_db)):
    admin_emails = [
        rec.email
        for rec in db.query(NotificationEmail).filter(NotificationEmail.verified.is_(True)).all()
    ]

    if not admin_emails:
        fallback = os.getenv("DEFAULT_NOTIFICATION_EMAIL") or os.getenv("RESEND_REPLY_TO")
        if fallback:
            admin_emails = [fallback]

    if not admin_emails:
        raise HTTPException(status_code=400, detail="No hay correos de notificación configurados")

    ok = await send_contact_email(form.model_dump(), admin_emails)
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo enviar el mensaje")

    return {"message": "Mensaje enviado"}
