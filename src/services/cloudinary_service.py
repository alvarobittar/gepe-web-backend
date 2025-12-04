"""
Cloudinary service for uploading and managing images.
"""
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
import os

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)


async def upload_image(file: UploadFile, folder: str = "gepe") -> dict:
    """
    Upload an image to Cloudinary.
    
    Args:
        file: The uploaded file from FastAPI
        folder: The folder in Cloudinary to store the image
    
    Returns:
        dict with 'url' (secure URL) and 'public_id'
    """
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
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception:
        return False
