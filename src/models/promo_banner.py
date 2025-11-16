from sqlalchemy import Column, Integer, String, Boolean, DateTime, func

from ..database import Base


class PromoBanner(Base):
    __tablename__ = "promo_banners"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


