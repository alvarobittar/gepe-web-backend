import os

class Settings:
    """Configuración de la aplicación que lee variables de entorno dinámicamente."""
    
    @property
    def app_name(self) -> str:
        return "GEPE Web Backend"
    
    @property
    def environment(self) -> str:
        # Detectar producción por variables de Railway o ENV
        env = os.getenv("ENV", "").lower()
        railway_env = os.getenv("RAILWAY_ENVIRONMENT", "").lower()
        # Si está en Railway (tiene PORT) o ENV=production, es producción
        if env == "production" or railway_env == "production" or os.getenv("PORT"):
            return "production"
        return "development"
    
    @property
    def cors_origin(self) -> str:
        return os.getenv("CORS_ORIGIN", "http://localhost:3000")
    
    @property
    def mp_access_token(self) -> str:
        return os.getenv("MP_ACCESS_TOKEN", "")
    
    @property
    def mp_webhook_url(self) -> str:
        return os.getenv("MP_WEBHOOK_URL", "")

# Instancia singleton de Settings (sin cache, lee valores dinámicamente)
_settings_instance = None

def get_settings() -> Settings:
    """Retorna la instancia de Settings. Lee variables de entorno dinámicamente."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance

def clear_settings_cache():
    """Limpia la instancia de settings (aunque no es necesario con propiedades dinámicas)."""
    global _settings_instance
    _settings_instance = None
