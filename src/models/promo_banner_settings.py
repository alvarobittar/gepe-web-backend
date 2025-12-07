from sqlalchemy import Column, Integer, DateTime, func

from ..database import Base


class PromoBannerSettings(Base):
    __tablename__ = "promo_banner_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    change_interval_seconds = Column(Integer, default=4, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

