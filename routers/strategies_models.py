from enum import Enum
from typing import Any, Dict, Optional, Union, List
from pydantic import BaseModel, Field
from decimal import Decimal
from hummingbot.strategy_v2.controllers import MarketMakingControllerConfigBase, ControllerConfigBase, DirectionalTradingControllerConfigBase
import importlib
import os
import logging
import functools

from pydantic.fields import ModelField
from pydantic.main import ModelMetaclass

logger = (
    logging.getLogger(__name__)
    if __name__ != "__main__"
    else logging.getLogger("uvicorn")
)

class StrategyType(str, Enum):
    DIRECTIONAL_TRADING = "directional_trading"
    MARKET_MAKING = "market_making"
    GENERIC = "generic"

class StrategyMapping(BaseModel):
    """Maps a strategy ID to its implementation details"""
    id: str  # e.g., "supertrend_v1"
    config_class: str  # e.g., "supertrendconfig"
    module_path: str  # e.g., "bots.controllers.directional_trading.supertrend_v1"
    strategy_type: StrategyType
    display_name: str  # e.g., "Supertrend V1"
    description: str = ""

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
    is_integer: bool = False
    display_type: str = Field(default="input", description="Can be 'input', 'slider', 'dropdown', 'toggle', or 'date'")

class StrategyConfig(BaseModel):
    """Complete strategy configuration including metadata and parameters"""
    mapping: StrategyMapping
    parameters: Dict[str, StrategyParameter]

class ParameterSuggestionRequest(BaseModel):
    strategy_id: str
    parameters: Dict[str, Any]
    requested_parameters: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific parameters to get suggestions for. If not provided, will suggest values for all missing required parameters."
    )

class ParameterSuggestion(BaseModel):
    parameter_name: str
    suggested_value: str
    reasoning: str
    differs_from_default: bool = False
    differs_from_provided: bool = False

class ParameterSuggestionResponse(BaseModel):
    suggestions: List[ParameterSuggestion]
    summary: str

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

    # structure of field
    client_data = field.field_info.extra.get('client_data')
    if client_data is not None and param.prompt == "":
        desc = client_data.prompt(None) if callable(client_data.prompt) else client_data.prompt
        if desc is not None:
            param.prompt = desc
        if not param.required:
            param.required = client_data.prompt_on_new if hasattr(client_data, 'prompt_on_new') else param.required
    param.display_type = "input"
    
    # Check for gt (greater than) and lt (less than) in field definition
    if hasattr(field.field_info, 'ge'):
        param.min_value = field.field_info.ge
    elif hasattr(field.field_info, 'gt'):
        param.min_value = field.field_info.gt + (1 if isinstance(field.field_info.gt, int) else Decimal('0'))

    if hasattr(field.field_info, 'le'):
        param.max_value = field.field_info.le
    elif hasattr(field.field_info, 'lt'):
        param.max_value = field.field_info.lt - (1 if isinstance(field.field_info.lt, int) else Decimal('0'))

    
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
        param.min_value = 0
    if param.type == "int":
        param.is_integer = True
    if any(word in name.lower() for word in ["executors", "workers"]):
        param.display_type = "slider"
        param.min_value = 1
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

def snake_case_to_real_name(snake_case: str) -> str:
    return " ".join([word.capitalize() for word in snake_case.split("_")])

def infer_strategy_type(module_path: str, config_class: Any) -> StrategyType:
    """Infer the strategy type from the module path and config class"""
    if "directional_trading" in module_path:
        return StrategyType.DIRECTIONAL_TRADING
    elif "market_making" in module_path:
        return StrategyType.MARKET_MAKING
    else:
        return StrategyType.GENERIC

def generate_strategy_mapping(module_path: str, config_class: Any) -> StrategyMapping:
    """Generate a strategy mapping from a config class"""
    # Extract strategy ID from module path (e.g., "supertrend_v1" from "bots.controllers.directional_trading.supertrend_v1")
    strategy_id = module_path.split(".")[-1]

    # Get strategy type
    strategy_type = infer_strategy_type(module_path, config_class)

    # Generate display name
    display_name = " ".join(word.capitalize() for word in strategy_id.split("_"))

    # Get description from class docstring
    description = config_class.__doc__ or ""

    return StrategyMapping(
        id=strategy_id,
        config_class=config_class.__name__,
        module_path=module_path,
        strategy_type=strategy_type,
        display_name=display_name,
        description=description
    )

@functools.lru_cache(maxsize=1)
def discover_strategies() -> Dict[str, StrategyConfig]:
    """Discover and load all available strategies"""
    strategy_configs = {}
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

                            # Generate mapping
                            mapping = generate_strategy_mapping(module_path, obj)

                            # Convert parameters
                            parameters = {}
                            for field_name, field in obj.__fields__.items():
                                param = convert_to_strategy_parameter(field_name, field)
                                parameters[field_name] = param
                            
                            # Create complete strategy config
                            strategy_configs[mapping.id] = StrategyConfig(
                                mapping=mapping,
                                parameters=parameters
                            )

                except ImportError as e:
                    logger.error(f"Error importing module {module_path}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error processing {module_path}: {e}")
                    import traceback
                    traceback.print_exc()

    return strategy_configs

def get_strategy_mapping(strategy_id: str) -> Optional[StrategyMapping]:
    """Get strategy mapping by ID"""
    strategies = discover_strategies()
    strategy = strategies.get(strategy_id)
    return strategy.mapping if strategy else None

def get_strategy_module_path(strategy_id: str) -> Optional[str]:
    """Get the module path for a strategy"""
    mapping = get_strategy_mapping(strategy_id)
    return mapping.module_path if mapping else None

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
