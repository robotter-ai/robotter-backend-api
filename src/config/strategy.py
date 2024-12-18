from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import json
from pathlib import Path

from .settings import get_settings


class StrategyConfig(BaseModel):
    name: str
    parameters: Dict[str, Any]
    risk_level: int = Field(ge=1, le=10)
    description: Optional[str] = None
    version: str = "1.0.0"
    
    class Config:
        extra = "forbid"  # Prevent typos in config


class StrategyConfigurationError(Exception):
    """Raised when there's an error loading strategy configurations."""
    pass


def load_strategies() -> Dict[str, StrategyConfig]:
    """
    Load and validate all strategy configurations.
    
    Returns:
        Dict[str, StrategyConfig]: Dictionary of strategy name to validated config
    
    Raises:
        StrategyConfigurationError: If there's an error loading or validating configs
    """
    settings = get_settings()
    try:
        with open(settings.STRATEGIES_CONFIG) as f:
            raw_config = json.load(f)
        
        return {
            name: StrategyConfig(name=name, **config)
            for name, config in raw_config.items()
        }
    except (json.JSONDecodeError, FileNotFoundError) as e:
        raise StrategyConfigurationError(f"Failed to load strategy config: {str(e)}")
    except Exception as e:
        raise StrategyConfigurationError(f"Invalid strategy configuration: {str(e)}") 