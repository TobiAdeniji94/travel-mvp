import os
from pathlib import Path
from typing import Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DB_URL: str = "postgresql://postgres:password@db:5432/traveldb"
    DB_ECHO: bool = False  # Set to True for SQL query logging in development
    
    # Connection Pool Settings
    DB_POOL_SIZE: int = 10  # Number of connections to maintain in pool
    DB_MAX_OVERFLOW: int = 20  # Maximum overflow connections beyond pool_size
    DB_POOL_TIMEOUT: int = 30  # Timeout in seconds to get connection from pool
    DB_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour
    
    # API Keys
    google_maps_api_key: str = ""
    openweather_api_key: str = ""
    
    # ML Models
    ML_MODELS_PATH: str = "/app/models"
    ENABLE_ML_CACHING: bool = True
    # Transformer Inference
    ENABLE_TRANSFORMER: bool = False
    TRANSFORMER_ARTIFACTS: str = "/app/ml/artifacts"
    
    # Rate Limiting
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_GENERATE: str = "5/minute"
    RATE_LIMIT_READ: str = "60/minute"
    RATE_LIMIT_LIST: str = "30/minute"
    RATE_LIMIT_UPDATE: str = "30/minute"
    RATE_LIMIT_DELETE: str = "10/minute"
    
    # Application Settings
    MAX_ITINERARY_DAYS: int = 30
    DEFAULT_RADIUS_KM: int = 20
    DEFAULT_BUDGET: float = 1000.0
    MAX_REQUEST_LENGTH: int = 2000
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "app.log"
    
    # CORS
    ALLOWED_ORIGINS: Union[list, str] = ["http://localhost:3000", "http://localhost:3001"]
    
    @field_validator('ALLOWED_ORIGINS', mode='before')
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse ALLOWED_ORIGINS from comma-separated string or list"""
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # Security
    JWT_SECRET: str = "change_me"
    JWT_REFRESH_SECRET: str = "refresh_change_me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Password Security
    PASSWORD_MIN_LENGTH: int = 6
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_NUMBER: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False
    
    # Security Features
    ENABLE_TOKEN_BLACKLIST: bool = True
    ENABLE_PASSWORD_VALIDATION: bool = True
    ENABLE_SECURITY_LOGGING: bool = True

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parents[3] / ".env"),
        env_file_encoding="utf-8",
    )
