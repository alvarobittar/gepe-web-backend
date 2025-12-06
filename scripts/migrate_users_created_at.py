"""
Script para agregar la columna created_at a la tabla users.
Ejecutar: python scripts/migrate_users_created_at.py
"""
import sqlite3
from datetime import datetime
import os

# Obtener el path del directorio del script y subir un nivel
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, "gepe.db")

def add_created_at_column():
    print(f"📂 Conectando a: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("❌ No se encontró la base de datos gepe.db")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar si la columna ya existe
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "created_at" in columns:
        print("✅ La columna 'created_at' ya existe en la tabla 'users'")
    else:
        print("➕ Agregando columna 'created_at' a la tabla 'users'...")
        # Agregar columna con valor por defecto
        default_date = datetime.utcnow().isoformat()
        cursor.execute(f"""
            ALTER TABLE users 
            ADD COLUMN created_at DATETIME DEFAULT '{default_date}'
        """)
        conn.commit()
        print("✅ Columna 'created_at' agregada exitosamente")
    
    # Mostrar estructura actual de la tabla
    cursor.execute("PRAGMA table_info(users)")
    print("\n📋 Estructura actual de la tabla 'users':")
    for col in cursor.fetchall():
        print(f"   - {col[1]} ({col[2]})")
    
    conn.close()

if __name__ == "__main__":
    add_created_at_column()
