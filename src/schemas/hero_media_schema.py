from datetime import datetime
from pydantic import BaseModel


class HeroMediaBase(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    highlight: str | None = None
    image_url: str
    video_url: str | None = None
    image_focus_x: int = 50
    image_focus_y: int = 50
    image_zoom: int = 100  # Zoom percentage (100 = normal, 150 = 1.5x zoom)
    is_active: bool = True
    display_order: int = 0
    show_overlay: bool = True  # Control darkening effect
    aspect_ratio_desktop: str = "16:6"  # Aspect ratio for desktop view
    aspect_ratio_mobile: str = "4:3"  # Aspect ratio for mobile view


class HeroMediaCreate(HeroMediaBase):
    pass


class HeroMediaUpdate(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    highlight: str | None = None
    image_url: str | None = None
    video_url: str | None = None
    image_focus_x: int | None = None
    image_focus_y: int | None = None
    image_zoom: int | None = None
    is_active: bool | None = None
    display_order: int | None = None
    show_overlay: bool | None = None
    aspect_ratio_desktop: str | None = None
    aspect_ratio_mobile: str | None = None


class HeroMediaOut(HeroMediaBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
