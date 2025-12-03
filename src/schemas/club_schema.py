from typing import Optional

from pydantic import BaseModel


class ClubBase(BaseModel):
    name: str
    slug: str
    city_key: str
    crest_image_url: Optional[str] = None


class ClubCreate(BaseModel):
    name: str
    city_key: str
    crest_image_url: Optional[str] = None


class ClubUpdate(BaseModel):
    name: Optional[str] = None
    city_key: Optional[str] = None
    crest_image_url: Optional[str] = None


class ClubOut(ClubBase):
    id: int

    class Config:
        orm_mode = True



