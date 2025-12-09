"""
Cloudinary service for uploading and managing images.
"""
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
import os

_cloudinary_configured = False


def _ensure_cloudinary_configured():
    """Configure Cloudinary lazily to ensure env vars are loaded."""
    global _cloudinary_configured
    if _cloudinary_configured:
        return
    
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )
    _cloudinary_configured = True


async def upload_image(file: UploadFile, folder: str = "gepe") -> dict:
    """
    Upload an image to Cloudinary.
    
    Args:
        file: The uploaded file from FastAPI
        folder: The folder in Cloudinary to store the image
    
    Returns:
        dict with 'url' (secure URL) and 'public_id'
    """
    _ensure_cloudinary_configured()
    try:
        # Read the file content
        contents = await file.read()
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="image",
            # Use original filename as part of public_id
            use_filename=True,
            unique_filename=True,
            # Optimize for web
            quality="auto",
            fetch_format="auto"
        )
        
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"]
        }
    except Exception as e:
        raise Exception(f"Error uploading to Cloudinary: {str(e)}")


async def upload_video(file: UploadFile, folder: str = "gepe") -> dict:
    """
    Upload a video to Cloudinary.
    """
    _ensure_cloudinary_configured()
    try:
        contents = await file.read()
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="video",
            use_filename=True,
            unique_filename=True,
            # Let Cloudinary optimize format/quality
            quality="auto",
            fetch_format="auto",
        )
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
        }
    except Exception as e:
        raise Exception(f"Error uploading video to Cloudinary: {str(e)}")


async def upload_club_crest(file: UploadFile) -> dict:
    """Upload a club crest image."""
    return await upload_image(file, folder="gepe/clubs")


async def upload_product_image(file: UploadFile) -> dict:
    """Upload a product image."""
    return await upload_image(file, folder="gepe/products")


def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary by its public_id.
    
    Args:
        public_id: The public ID of the image to delete
    
    Returns:
        True if deleted successfully
    """
    _ensure_cloudinary_configured()
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception:
        return False


def extract_public_id_from_url(url: str) -> str | None:
    """
    Extrae el public_id de una URL de Cloudinary.
    
    Formato de URL: https://res.cloudinary.com/{cloud_name}/image/upload/{version}/{folder}/{filename}.{ext}
    O: https://res.cloudinary.com/{cloud_name}/image/upload/{folder}/{filename}.{ext}
    
    Args:
        url: URL completa de la imagen en Cloudinary
    
    Returns:
        public_id o None si no se puede extraer
    """
    try:
        import re
        # Buscar el patrón /image/upload/ en la URL
        if "/image/upload/" not in url:
            return None
        
        # Extraer la parte después de /image/upload/
        parts = url.split("/image/upload/")[1]
        
        # Eliminar parámetros de consulta si existen (ej: ?resize=...)
        if "?" in parts:
            parts = parts.split("?")[0]
        
        # Eliminar cualquier parámetro de transformación o versión
        # Ejemplo: v1765061993/gepe/products/file_jkd7by.jpg
        # o: gepe/products/file_jkd7by.jpg
        
        # Si tiene versión (v1234567890), eliminarla
        if parts.startswith("v") and "/" in parts:
            # Buscar el primer número seguido de /
            parts = re.sub(r'^v\d+/', '', parts)
        
        # Eliminar la extensión del archivo
        public_id = parts.rsplit('.', 1)[0] if '.' in parts else parts
        
        return public_id
    except Exception as e:
        print(f"Error extrayendo public_id de URL: {url}, error: {e}")
        return None


def delete_image_from_url(url: str) -> bool:
    """
    Elimina una imagen de Cloudinary a partir de su URL.
    
    Args:
        url: URL completa de la imagen en Cloudinary
    
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    public_id = extract_public_id_from_url(url)
    if not public_id:
        return False
    return delete_image(public_id)