import os
from functools import lru_cache

class Settings:
    app_name: str = "GEPE Web Backend"
    environment: str = os.getenv("ENV", "development")
    cors_origin: str = os.getenv("CORS_ORIGIN", "http://localhost:3000")

@lru_cache
def get_settings() -> Settings:
    return Settings()
