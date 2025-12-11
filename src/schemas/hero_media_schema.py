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
    is_active: bool = True
    display_order: int = 0
    show_overlay: bool = True  # Control darkening effect


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
    is_active: bool | None = None
    display_order: int | None = None
    show_overlay: bool | None = None


class HeroMediaOut(HeroMediaBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
