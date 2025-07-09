import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DB_URL: str
    google_maps_api_key: str
    openweather_api_key: str

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parents[3] / ".env"),
        env_file_encoding="utf-8",
    )
