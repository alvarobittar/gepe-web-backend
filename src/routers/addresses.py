import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.address import Address
from ..models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/addresses", tags=["addresses"])


class AddressBase(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    label: Optional[str] = Field(None, description="Ej: Casa, Trabajo")
    address_line: str
    city: Optional[str] = None
    province: Optional[str] = None
    zip_code: Optional[str] = None
    is_default: Optional[bool] = False


class AddressCreate(AddressBase):
    email: str = Field(..., description="Email del usuario dueño de la dirección")


class AddressUpdate(AddressBase):
    pass


class AddressOut(AddressBase):
    id: int

    class Config:
        orm_mode = True


def get_or_create_user(db: Session, email: str, full_name: str = None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, full_name=full_name, hashed_password=None)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("", response_model=List[AddressOut])
def list_addresses(email: str = Query(..., description="Email del usuario"), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return []
    addresses = db.query(Address).filter(Address.user_id == user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
    return addresses


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(address_in: AddressCreate, db: Session = Depends(get_db)):
    user = get_or_create_user(db, address_in.email, address_in.full_name)

    if address_in.is_default:
        db.query(Address).filter(Address.user_id == user.id, Address.is_default == True).update({Address.is_default: False})  # noqa: E712

    address = Address(
        user_id=user.id,
        full_name=address_in.full_name,
        phone=address_in.phone,
        label=address_in.label,
        address_line=address_in.address_line,
        city=address_in.city,
        province=address_in.province,
        zip_code=address_in.zip_code,
        is_default=address_in.is_default or False,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.patch("/{address_id}", response_model=AddressOut)
def update_address(address_id: int, address_in: AddressUpdate, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dirección no encontrada")

    if address_in.is_default:
        db.query(Address).filter(Address.user_id == address.user_id, Address.id != address.id).update({Address.is_default: False})

    for field, value in address_in.dict(exclude_unset=True).items():
        setattr(address, field, value)

    db.commit()
    db.refresh(address)
    return address


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dirección no encontrada")
    db.delete(address)
    db.commit()
    return None


@router.post("/{address_id}/default", response_model=AddressOut)
def set_default(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dirección no encontrada")

    db.query(Address).filter(Address.user_id == address.user_id, Address.id != address.id).update({Address.is_default: False})
    address.is_default = True
    db.commit()
    db.refresh(address)
    return address

