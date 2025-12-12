"""
Modelo para suscriptores del newsletter.
Guarda emails para campañas de marketing.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from src.database import Base


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)  # Para manejar desuscripciones
    source = Column(String(50), default="footer")  # Dónde se suscribió (footer, popup, etc.)
