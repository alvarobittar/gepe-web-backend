from sqlalchemy import Column, Integer, String

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)

    # Nota: created_at removido porque la tabla existente no tiene esa columna
    # y no queremos ejecutar migraciones manuales.
