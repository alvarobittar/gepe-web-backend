"""
Servicio para notificar al frontend (Vercel) que debe revalidar páginas cacheadas.
Esto permite que los cambios en el admin se reflejen inmediatamente en la web.
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

# URL del frontend (Vercel)
FRONTEND_URL = os.getenv("FRONTEND_URL", os.getenv("CORS_ORIGIN", "http://localhost:3000"))
REVALIDATE_SECRET = os.getenv("REVALIDATE_SECRET", "gepe-revalidate-secret-2024")


async def revalidate_frontend(
    type: str | None = None,
    paths: list[str] | None = None,
    tags: list[str] | None = None
) -> bool:
    """
    Notifica al frontend que debe revalidar ciertas páginas.
    
    Args:
        type: Tipo de contenido cambiado ("product", "club", "prices", "hero")
        paths: Lista de paths específicos a revalidar (ej: ["/producto/camiseta-river"])
        tags: Lista de tags a revalidar
    
    Returns:
        True si la revalidación fue exitosa, False en caso contrario
    """
    try:
        url = f"{FRONTEND_URL.rstrip('/')}/api/revalidate"
        
        payload = {
            "secret": REVALIDATE_SECRET,
        }
        
        if type:
            payload["type"] = type
        if paths:
            payload["paths"] = paths
        if tags:
            payload["tags"] = tags
            
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[Revalidate] Success: {data.get('items', [])}")
                return True
            else:
                logger.warning(f"[Revalidate] Failed with status {response.status_code}: {response.text}")
                return False
                
    except httpx.TimeoutException:
        logger.warning("[Revalidate] Timeout - frontend may be slow or unavailable")
        return False
    except Exception as e:
        # No queremos que falle la operación principal si la revalidación falla
        logger.warning(f"[Revalidate] Error: {e}")
        return False


async def revalidate_product(slug: str | None = None):
    """Revalida páginas relacionadas con productos."""
    paths = ["/"]  # Home siempre
    if slug:
        paths.append(f"/producto/{slug}")
    return await revalidate_frontend(type="products", paths=paths)


async def revalidate_club(slug: str | None = None):
    """Revalida páginas relacionadas con clubes."""
    paths = ["/"]  # Home siempre
    if slug:
        paths.append(f"/clubes/{slug}")
    return await revalidate_frontend(type="clubs", paths=paths)


async def revalidate_prices():
    """Revalida páginas que muestran precios."""
    return await revalidate_frontend(type="prices")


async def revalidate_hero():
    """Revalida el home (hero carousel)."""
    return await revalidate_frontend(type="hero")
