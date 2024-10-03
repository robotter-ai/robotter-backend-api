from typing import Any, Dict, Optional, Union, List
from pydantic import BaseModel, Field
from decimal import Decimal
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_decimal, validate_int, validate_bool,
    validate_float, validate_exchange, validate_market_trading_pair,
    validate_connector
)

class StrategyParameter(BaseModel):
    name: str
    type: str
    prompt: str
    default: Optional[Any]
    required: bool
    min_value: Optional[Union[int, float, Decimal]] = None
    max_value: Optional[Union[int, float, Decimal]] = None
    valid_values: Optional[List[Any]] = None
    is_percentage: bool = False
    is_price: bool = False
    is_timespan: bool = False
    is_connector: bool = False
    is_trading_pair: bool = False
    display_type: str = Field(default="input", description="Can be 'input', 'slider', 'dropdown', 'toggle', or 'date'")

def extract_validator_info(validator, field_type):
    info = {}
    if isinstance(validator, (validate_decimal, validate_float, validate_int)):
        info["min_value"] = validator.min_value
        info["max_value"] = validator.max_value
        if field_type == "percentage":
            info["is_percentage"] = True
            info["display_type"] = "slider"
        elif field_type == "price":
            info["is_price"] = True
        elif field_type == "timespan":
            info["is_timespan"] = True
    elif isinstance(validator, validate_bool):
        info["valid_values"] = [True, False]
        info["display_type"] = "toggle"
    elif isinstance(validator, (validate_exchange, validate_connector)):
        info["valid_values"] = validator.valid_exchanges
        info["is_connector"] = True
        info["display_type"] = "dropdown"
    elif isinstance(validator, validate_market_trading_pair):
        info["is_trading_pair"] = True
    return info

def convert_config_to_strategy_format(config_map: Dict[str, ConfigVar]) -> Dict[str, StrategyParameter]:
    parameters = {}
    for key, config_var in config_map.items():
        prompt = config_var.prompt if isinstance(config_var.prompt, str) else ""
        if callable(config_var.prompt):
            try:
                prompt = config_var.prompt()
            except:
                prompt = ""
        
        prompt = prompt.replace('>>> ', '').strip()

        required = config_var.required if isinstance(config_var.required, bool) else False
        if callable(config_var.required):
            try:
                required = config_var.required()
            except:
                required = False

        validator_info = extract_validator_info(config_var.validator, config_var.type) if config_var.validator else {}

        param = StrategyParameter(
            name=key,
            type=config_var.type,
            prompt=prompt,
            default=config_var.default,
            required=required,
            **validator_info
        )
        parameters[key] = param
    
    return parameters