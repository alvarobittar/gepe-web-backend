from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime
from ..database import Base


class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    label = Column(String(100), nullable=True)  # Ej: Casa, Trabajo
    address_line = Column(String(500), nullable=False)
    city = Column(String(100), nullable=True)
    province = Column(String(100), nullable=True)
    zip_code = Column(String(20), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

