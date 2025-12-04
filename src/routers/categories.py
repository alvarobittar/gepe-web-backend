"""
Router para gestionar categorías de productos
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..models.product import Category, Product
from ..schemas.category_schema import CategoryCreate, CategoryUpdate, CategoryOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=List[CategoryOut])
async def list_categories(
    db: Session = Depends(get_db)
):
    """
    Lista todas las categorías ordenadas por nombre.
    """
    try:
        categories = db.query(Category).order_by(Category.name).all()
        return categories
    except Exception as e:
        logger.error(f"Error al listar categorías: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las categorías: {str(e)}"
        )


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene una categoría específica por ID.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría {category_id} no encontrada"
        )
    
    return category


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una nueva categoría.
    """
    try:
        # Verificar si ya existe una categoría con el mismo nombre o slug
        existing = db.query(Category).filter(
            (Category.name == category_data.name) | (Category.slug == category_data.slug)
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una categoría con el nombre '{category_data.name}' o slug '{category_data.slug}'"
            )
        
        category = Category(
            name=category_data.name,
            slug=category_data.slug
        )
        
        db.add(category)
        db.commit()
        db.refresh(category)
        
        logger.info(f"Categoría creada: {category.name} (ID: {category.id})")
        return category
        
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error de integridad al crear categoría: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una categoría con ese nombre o slug"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error al crear categoría: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear la categoría: {str(e)}"
        )


@router.put("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza una categoría existente.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría {category_id} no encontrada"
        )
    
    try:
        # Verificar si el nuevo nombre o slug ya existe en otra categoría
        if category_data.name or category_data.slug:
            existing = db.query(Category).filter(
                Category.id != category_id,
                (
                    (Category.name == (category_data.name or category.name)) |
                    (Category.slug == (category_data.slug or category.slug))
                )
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya existe otra categoría con ese nombre o slug"
                )
        
        # Actualizar campos
        if category_data.name is not None:
            category.name = category_data.name
        if category_data.slug is not None:
            category.slug = category_data.slug
        
        db.commit()
        db.refresh(category)
        
        logger.info(f"Categoría actualizada: {category.name} (ID: {category.id})")
        return category
        
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error de integridad al actualizar categoría: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe otra categoría con ese nombre o slug"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error al actualizar categoría: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar la categoría: {str(e)}"
        )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina una categoría.
    No se puede eliminar si tiene productos asociados.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría {category_id} no encontrada"
        )
    
    # Verificar si hay productos asociados
    products_count = db.query(Product).filter(Product.category_id == category_id).count()
    
    if products_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar la categoría porque tiene {products_count} producto(s) asociado(s). Primero debes cambiar o eliminar esos productos."
        )
    
    try:
        db.delete(category)
        db.commit()
        
        logger.info(f"Categoría eliminada: {category.name} (ID: {category_id})")
        return None
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al eliminar categoría: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar la categoría: {str(e)}"
        )




