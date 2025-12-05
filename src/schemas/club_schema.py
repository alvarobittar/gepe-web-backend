from typing import Optional

from pydantic import BaseModel


class ClubBase(BaseModel):
    name: str
    slug: str
    city_key: str
    crest_image_url: Optional[str] = None
    display_name: Optional[str] = None
    is_active: bool = True


class ClubCreate(BaseModel):
    name: str
    city_key: str
    crest_image_url: Optional[str] = None
    display_name: Optional[str] = None
    is_active: bool = True


class ClubUpdate(BaseModel):
    name: Optional[str] = None
    city_key: Optional[str] = None
    crest_image_url: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class ClubOut(ClubBase):
    id: int

    model_config = {"from_attributes": True}
