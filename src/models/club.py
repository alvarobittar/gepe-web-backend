from sqlalchemy import Column, Integer, String

from ..database import Base


class Club(Base):
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, index=True, nullable=False)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    # Clave de ciudad, ej: sanRafael, generalAlvear, malargue, sanLuis, mendoza, neuquen
    city_key = Column(String(50), index=True, nullable=False)
    # URL relativa o absoluta del escudo (se usará en el carrusel)
    crest_image_url = Column(String(500), nullable=True)





