from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    model_config  = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    APP_NAME: str = "Portal Alcaldía API"
    ENV: str = "dev"
    DATA_DIR: str = Field(default=os.getenv("DATA_DIR", "./data"))
    DB_PATH: str = Field(default=os.getenv("DB_PATH", "./data/current/duckdb.db"))
    ADMIN_TOKEN: str = "change_me"
    LOG_LEVEL: str = "INFO"

settings = Settings()
