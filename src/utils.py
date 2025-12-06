import re


def slugify(text: str) -> str:
    """
    Genera un slug a partir de un texto, normalizando tildes y caracteres especiales.
    
    Ejemplos:
    - "Club Atlético San Luis" -> "club-atletico-san-luis"
    - "Camiseta Élite" -> "camiseta-elite"
    """
    if not text:
        return ""
    
    slug = text.lower().strip()
    
    # Normalizar tildes y caracteres especiales
    slug = (
        slug.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
        .replace("ü", "u")
    )
    
    # Reemplazar cualquier carácter que no sea letra, número o espacio con un guión
    slug = re.sub(r"[^a-z0-9\s]+", "-", slug)
    
    # Reemplazar espacios y múltiples guiones consecutivos con un solo guión
    slug = re.sub(r"[\s\-]+", "-", slug)
    
    # Eliminar guiones al inicio y al final
    slug = slug.strip("-")
    
    return slug


