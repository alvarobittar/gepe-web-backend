from sqlalchemy import Column, Integer, String, Boolean, DateTime, func

from ..database import Base


class HeroMedia(Base):
    __tablename__ = "hero_media"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)  # Now optional
    subtitle = Column(String(255), nullable=True)
    highlight = Column(String(255), nullable=True)
    image_url = Column(String(500), nullable=False)
    video_url = Column(String(2000), nullable=True)
    # Focus point for image cropping (0-100, where 50,50 is center)
    image_focus_x = Column(Integer, default=50)
    image_focus_y = Column(Integer, default=50)
    # Zoom level (100 = normal, 150 = 1.5x zoom in)
    image_zoom = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    show_overlay = Column(Boolean, default=True)  # Darkening effect toggle
    # Aspect ratios for responsive display
    aspect_ratio_desktop = Column(String(10), default="16:6")
    aspect_ratio_mobile = Column(String(10), default="4:3")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
