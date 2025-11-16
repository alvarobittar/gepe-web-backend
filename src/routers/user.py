from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/user", tags=["user"])


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None


@router.get("/me", response_model=UserOut)
def get_me():
    """
    MVP de perfil de usuario sin autenticación real.
    Devolvemos un usuario invitado fijo.
    """
    return UserOut(id=1, email="invitado@gepe.com", full_name="Invitado GEPE")


