from datetime import datetime
from pydantic import BaseModel


class PromoBannerBase(BaseModel):
    message: str
    is_active: bool = True
    display_order: int = 0


class PromoBannerCreate(PromoBannerBase):
    pass


class PromoBannerUpdate(BaseModel):
    message: str | None = None
    is_active: bool | None = None
    display_order: int | None = None


class PromoBannerOut(PromoBannerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromoBannerSettingsOut(BaseModel):
    change_interval_seconds: int

    class Config:
        from_attributes = True


class PromoBannerSettingsUpdate(BaseModel):
    change_interval_seconds: int


