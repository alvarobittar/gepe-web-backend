#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para actualizar el rol de un usuario de 'cliente' a 'admin' en la base de datos.
Este script actualiza el campo 'role' en la tabla 'user' de betterAuth.
"""

import sqlite3
import sys
import io
from pathlib import Path

# Configurar stdout para UTF-8 en Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ruta a la base de datos
DB_PATH = Path(__file__).parent / "gepe.db"

# Datos del usuario a actualizar
USER_EMAIL = "alvarobittar19950@gmail.com"
USER_ID = "uPVMYk7rUvqc8TLxbqKCdgCR1wXVKrZu"
NEW_ROLE = "admin"


def update_user_role():
    """Actualiza el rol del usuario en la base de datos."""
    try:
        # Conectar a la base de datos
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar que el usuario existe
        cursor.execute(
            "SELECT id, email, role FROM user WHERE id = ? OR email = ?",
            (USER_ID, USER_EMAIL)
        )
        user = cursor.fetchone()
        
        if not user:
            print(f"[ERROR] No se encontro el usuario con ID '{USER_ID}' o email '{USER_EMAIL}'")
            return False
        
        user_id, user_email, current_role = user
        print(f"[OK] Usuario encontrado:")
        print(f"   ID: {user_id}")
        print(f"   Email: {user_email}")
        print(f"   Rol actual: {current_role}")
        
        # Actualizar el rol
        cursor.execute(
            "UPDATE user SET role = ? WHERE id = ?",
            (NEW_ROLE, user_id)
        )
        
        # Confirmar los cambios
        conn.commit()
        
        # Verificar que se actualizó correctamente
        cursor.execute("SELECT role FROM user WHERE id = ?", (user_id,))
        updated_role = cursor.fetchone()[0]
        
        if updated_role == NEW_ROLE:
            print(f"[OK] Rol actualizado exitosamente a '{NEW_ROLE}'")
            conn.close()
            return True
        else:
            print(f"[ERROR] El rol no se actualizo correctamente. Rol actual: {updated_role}")
            conn.close()
            return False
            
    except sqlite3.Error as e:
        print(f"[ERROR] Error de base de datos: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        if conn:
            conn.close()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Script de actualización de rol de usuario")
    print("=" * 60)
    print(f"Base de datos: {DB_PATH.absolute()}")
    print(f"Email del usuario: {USER_EMAIL}")
    print(f"ID del usuario: {USER_ID}")
    print(f"Nuevo rol: {NEW_ROLE}")
    print("=" * 60)
    print()
    
    success = update_user_role()
    
    if success:
        print()
        print("[OK] Proceso completado exitosamente")
        sys.exit(0)
    else:
        print()
        print("[ERROR] El proceso fallo")
        sys.exit(1)

