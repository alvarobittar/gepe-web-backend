import re


def slugify(text: str) -> str:
    """
    Genera un slug a partir de un texto, normalizando tildes y caracteres especiales.
    
    Ejemplos:
    - "Club Atlético San Luis" -> "club-atletico-san-luis"
    - "Camiseta Élite" -> "camiseta-elite"
    - "San Martín de Monte Comán" -> "san-martin-de-monte-coman"
    """
    import unicodedata
    
    if not text:
        return ""
    
    # Convertir a minúsculas y eliminar espacios al inicio/final
    slug = text.lower().strip()
    
    # Normalizar Unicode: NFD separa caracteres base de diacríticos
    slug = unicodedata.normalize('NFD', slug)
    
    # Eliminar diacríticos (tildes, acentos)
    slug = ''.join(char for char in slug if unicodedata.category(char) != 'Mn')
    
    # Reemplazar espacios por guiones
    slug = re.sub(r'\s+', '-', slug)
    
    # Eliminar cualquier carácter que no sea letra, número o guión
    slug = re.sub(r'[^a-z0-9\-]+', '', slug)
    
    # Reemplazar múltiples guiones consecutivos con uno solo
    slug = re.sub(r'\-+', '-', slug)
    
    # Eliminar guiones al inicio y al final
    slug = slug.strip('-')
    
    return slug


