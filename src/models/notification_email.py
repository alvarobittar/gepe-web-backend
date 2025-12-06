from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime

from ..database import Base


class NotificationEmail(Base):
    __tablename__ = "notification_emails"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
