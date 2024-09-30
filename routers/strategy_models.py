from typing import Dict, Any, Optional, Union
from pydantic import BaseModel
from hummingbot.client.config.config_var import ConfigVar

class StrategyParameter(BaseModel):
    type: str
    prompt: str
    default: Optional[Any]
    required: bool

class Strategy(BaseModel):
    name: str
    parameters: Dict[str, StrategyParameter]

def convert_config_to_strategy_format(config_map: Dict[str, ConfigVar]) -> Strategy:
    parameters = {}
    for key, config_var in config_map.items():
        prompt = config_var.prompt if isinstance(config_var.prompt, str) else ""
        if callable(config_var.prompt):
            try:
                prompt = config_var.prompt()
            except:
                prompt = ""
        
        prompt = prompt.replace('>>> ', '').strip()

        try:
            required = bool(config_var.required)
        except:
            required = False

        param = StrategyParameter(
            type=config_var.type,
            prompt=prompt,
            default=config_var.default,
            required=required
        )
        parameters[key] = param
    
    return Strategy(name="pure_market_making", parameters=parameters)