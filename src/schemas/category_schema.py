from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
import re


def generate_slug(name: str) -> str:
    """Genera un slug a partir de un nombre."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


class CategoryCreate(BaseModel):
    name: str
    slug: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('El nombre de la categoría no puede estar vacío')
        if len(v) > 100:
            raise ValueError('El nombre de la categoría no puede tener más de 100 caracteres')
        return v.strip()

    @model_validator(mode='after')
    def generate_slug_if_needed(self):
        # Generar slug automáticamente si no se proporciona
        if not self.slug:
            self.slug = generate_slug(self.name)
        return self


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError('El nombre de la categoría no puede estar vacío')
            if len(v) > 100:
                raise ValueError('El nombre de la categoría no puede tener más de 100 caracteres')
            return v.strip()
        return v

    @model_validator(mode='after')
    def generate_slug_if_needed(self):
        # Generar slug automáticamente si se actualiza el nombre pero no el slug
        if self.name and not self.slug:
            self.slug = generate_slug(self.name)
        return self


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True

