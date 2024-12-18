from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Any, Dict, Optional
from enum import Enum
import json
from functools import lru_cache


class Environment(str, Enum):
    DEV = "development"
    PROD = "production"
    TEST = "test"


class Settings(BaseSettings):
    # Environment
    ENV: Environment = Environment.DEV
    DEBUG: bool = False
    
    # API Keys and Security
    BIRDEYE_API_KEY: str
    FASTAPI_WALLETAUTH_PRIVATE_KEY: str
    GATEWAY_CERT_PASSPHRASE: str
    CONFIG_PASSWORD: str
    
    # Paths (relative to project root)
    BOTS_PATH: Path = Path("bots")
    CERTS_PATH: Path = Path("certs")
    
    # Trading Configuration
    STRATEGIES_CONFIG: Path = Path("strategies.json")
    
    # API Configuration
    CORS_ORIGINS: list[str] = ["*"]
    API_V1_PREFIX: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            if field_name.endswith("_PATH"):
                return Path(raw_val).resolve()
            if field_name == "CORS_ORIGINS" and raw_val == "*":
                return ["*"]
            return raw_val


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings() 