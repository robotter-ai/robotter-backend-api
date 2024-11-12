from enum import Enum
from typing import Any, Dict, Optional, Union, List

from hummingbot.core.data_type.common import PositionMode
from pydantic import BaseModel, Field
from decimal import Decimal
from hummingbot.strategy_v2.controllers import MarketMakingControllerConfigBase, ControllerConfigBase, DirectionalTradingControllerConfigBase
import importlib
import os
import logging
import functools

from pydantic.fields import ModelField
from pydantic.main import ModelMetaclass

from bots.controllers.directional_trading.bollinger_v1 import BollingerV1ControllerConfig

logger = (
    logging.getLogger(__name__)
    if __name__ != "__main__"
    else logging.getLogger("uvicorn")
)

class StrategyParameter(BaseModel):
    name: str
    group: str
    is_advanced: bool = False
    pretty_name: str
    description: str
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


def is_advanced_parameter(name: str) -> bool:
    advanced_keywords = [
        "activation_bounds", "triple_barrier", "leverage", "dca", "macd", "natr",
        "multiplier", "imbalance", "executor", "perp", "arbitrage"
    ]
    
    simple_keywords = [
        "controller_name", "candles", "interval", "stop_loss", "take_profit",
        "buy", "sell", "position_size", "time_limit", "spot"
    ]
    
    name_lower = name.lower()
    
    if any(keyword in name_lower for keyword in advanced_keywords):
        return True
    
    if any(keyword in name_lower for keyword in simple_keywords):
        return False
    
    return True

def get_strategy_display_info() -> Dict[str, Dict[str, str]]:
    """
    Returns user-friendly names and descriptions for each strategy
    """
    return {
        # Directional Trading Strategies
        "bollinger_v1": {
            "pretty_name": "Bollinger Bands Strategy",
            "description": "Buys when price is low and sells when price is high based on Bollinger Bands."
        },
        "dman_v3": {
            "pretty_name": "Smart DCA Strategy",
            "description": "Automatically adjusts buy/sell levels based on market conditions with multiple take-profit targets."
        },
        "macd_bb_v1": {
            "pretty_name": "MACD + Bollinger Strategy",
            "description": "Uses two popular indicators to find better entry and exit points for trades."
        },
        "supertrend_v1": {
            "pretty_name": "SuperTrend Strategy",
            "description": "Follows market trends to find good times to buy and sell."
        },
        
        # Market Making Strategies
        "dman_maker_v2": {
            "pretty_name": "Smart Market Maker",
            "description": "Places buy and sell orders that automatically adjust to market conditions."
        },
        "pmm_dynamic": {
            "pretty_name": "Dynamic Market Maker",
            "description": "Places orders with spreads that adapt to market volatility."
        },
        "pmm_simple": {
            "pretty_name": "Simple Market Maker",
            "description": "Places basic buy and sell orders with fixed spreads."
        },
        
        # Generic Strategies
        "spot_perp_arbitrage": {
            "pretty_name": "Spot-Futures Arbitrage",
            "description": "Profits from price differences between spot and futures markets."
        },
        "xemm_multiple_levels": {
            "pretty_name": "Multi-Exchange Market Maker",
            "description": "Places orders across different exchanges to capture price differences."
        }
    }

def convert_to_strategy_parameter(name: str, field: ModelField) -> StrategyParameter:
    param = StrategyParameter(
        name=name,
        type=str(field.type_.__name__),
        prompt=field.description if hasattr(field, 'description') else "",
        default=field.default,
        required=field.required or field.default is not None,
        is_advanced=is_advanced_parameter(name),
        group=determine_parameter_group(name),
        pretty_name=name.replace('_', ' ').title(),  
        description="",  
    )
    
    # Get strategy display info
    strategy_info = get_strategy_display_info()
    
    # Try to find matching strategy info
    for strategy_name, info in strategy_info.items():
        if strategy_name in name.lower():
            param.pretty_name = info["pretty_name"]
            param.description = info["description"]
            break
    
    if hasattr(field, 'client_data'):
        client_data = field.client_data
        if param.prompt == "":
            param.prompt = client_data.prompt() if callable(client_data.prompt) else client_data.prompt
        if not param.required:
            param.required = client_data.prompt_on_new if hasattr(client_data, 'prompt_on_new') else param.required
    param.display_type = "input"
    
    # Check for gt (greater than) and lt (less than) in field definition
    if hasattr(field.field_info, 'gt'):
        param.min_value = field.field_info.gt
    if hasattr(field.field_info, 'lt'):
        param.max_value = field.field_info.lt
    
    # Set display_type to "slider" only if both min and max values are present
    if param.min_value is not None and param.max_value is not None:
        param.display_type = "slider"
    elif param.type == "bool":
        param.display_type = "toggle"
    
    if "connector" in name.lower():
        param.is_connector = True
    if "trading_pair" in name.lower():
        param.is_trading_pair = True
    if any(word in name.lower() for word in ["percentage", "percent", "ratio", "pct"]):
        param.is_percentage = True
    if "price" in name.lower():
        param.is_price = True
        if param.min_value is None:
            param.min_value = Decimal(0)
    if "amount" in name.lower():
        param.min_value = Decimal(0)
    if any(word in name.lower() for word in ["time", "interval", "duration"]):
        param.is_timespan = True
    try:
        if issubclass(field.type_, Enum):
            param.valid_values = [item.value for item in field.type_]
            param.display_type = "dropdown"
    except:
        pass
    return param

def determine_parameter_group(name: str) -> str:
    if any(word in name.lower() for word in ["controller_name", "candles", "interval"]):
        return "General Settings"
    elif any(word in name.lower() for word in ["stop_loss", "trailing_stop", "take_profit", "activation_bounds", "leverage", "triple_barrier"]):
        return "Risk Management"
    elif "buy" in name.lower():
        return "Buy Order Settings"
    elif "sell" in name.lower():
        return "Sell Order Settings"
    elif "dca" in name.lower():
        return "DCA Settings"
    elif any(word in name.lower() for word in ["bb", "macd", "natr", "length", "multiplier"]):
        return "Indicator Settings"
    elif any(word in name.lower() for word in ["profitability", "position_size"]):
        return "Profitability Settings"
    elif any(word in name.lower() for word in ["time_limit", "executor", "imbalance"]):
        return "Execution Settings"
    elif any(word in name.lower() for word in ["spot", "perp"]):
        return "Arbitrage Settings"
    else:
        return "Other"


@functools.lru_cache(maxsize=1)
def get_all_strategy_maps() -> Dict[str, Dict[str, StrategyParameter]]:
    strategy_maps = {}
    controllers_dir = "bots/controllers"
    
    for root, dirs, files in os.walk(controllers_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                module_path = os.path.join(root, file).replace("/", ".").replace("\\", ".")[:-3]
                module_path = f"bots.{module_path.split('bots.')[-1]}"
                
                try:
                    module = importlib.import_module(module_path)
                    
                    for name, obj in module.__dict__.items():
                        if (
                            isinstance(obj, type)
                            and issubclass(obj, ControllerConfigBase)
                            and obj is not ControllerConfigBase
                            and obj is not MarketMakingControllerConfigBase
                            and obj is not DirectionalTradingControllerConfigBase
                        ):
                            assert isinstance(obj, ModelMetaclass)
                            strategy_name = obj.controller_name if hasattr(obj, 'controller_name') else name.lower()
                            parameters = {}
                            for field_name, field in obj.__fields__.items():
                                param = convert_to_strategy_parameter(field_name, field)
                                parameters[field_name] = param
                            
                            strategy_maps[strategy_name] = parameters
                except ImportError as e:
                    print(f"Error importing module {module_path}: {e}")
                except Exception as e:
                    print(f"Unexpected error processing {module_path}: {e}")
                    import traceback
                    traceback.print_exc()
    return strategy_maps
