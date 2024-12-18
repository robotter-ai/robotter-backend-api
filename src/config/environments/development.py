"""Development environment specific settings."""

from typing import Dict, Any

settings: Dict[str, Any] = {
    "DEBUG": True,
    "LOG_LEVEL": "DEBUG",
    "CORS_ORIGINS": ["*"],  # Allow all origins in development
    "HOT_RELOAD": True,
} 