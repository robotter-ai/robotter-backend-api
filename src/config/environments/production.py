"""Production environment specific settings."""

from typing import Dict, Any

settings: Dict[str, Any] = {
    "DEBUG": False,
    "LOG_LEVEL": "WARNING",
    "CORS_ORIGINS": [],  # Should be set via environment variable in production
    "HOT_RELOAD": False,
} 