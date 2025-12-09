"""
Script para regenerar los slugs de todos los productos.
Ejecutar desde el directorio backend con: python regenerate_slugs.py

Este script usa acceso directo a SQLite para evitar problemas de imports.
"""

import sqlite3
import unicodedata
import re
import os


def slugify(text: str) -> str:
    """
    Genera un slug a partir de un texto, normalizando tildes y caracteres especiales.
    """
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


def regenerate_slugs():
    """Regenera los slugs de todos los productos usando la función slugify mejorada."""
    
    # Buscar el archivo de base de datos
    db_path = os.path.join(os.path.dirname(__file__), 'gepe.db')
    
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos en: {db_path}")
        return
    
    print(f"📦 Conectando a: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Obtener todos los productos
        cursor.execute("SELECT id, name, slug FROM products")
        products = cursor.fetchall()
        
        print(f"\nRegenerando slugs para {len(products)} productos...\n")
        
        updated_count = 0
        for product_id, name, old_slug in products:
            new_slug = slugify(name)
            
            if old_slug != new_slug:
                cursor.execute(
                    "UPDATE products SET slug = ? WHERE id = ?",
                    (new_slug, product_id)
                )
                updated_count += 1
                print(f"  ✓ {name}")
                print(f"    Antiguo: {old_slug}")
                print(f"    Nuevo:   {new_slug}\n")
        
        if updated_count > 0:
            conn.commit()
            print(f"✅ Regeneración completa. {updated_count} productos actualizados.")
        else:
            print("✅ Todos los slugs ya están correctos. No se necesitaron cambios.")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error al regenerar slugs: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    regenerate_slugs()
