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

class DisplayType(str, Enum):
    INPUT = "input"
    SLIDER = "slider"
    DROPDOWN = "dropdown"
    TOGGLE = "toggle"
    DATE = "date"

class ParameterType(str, Enum):
    PERCENTAGE = "percentage"
    PRICE = "price"
    TIMESPAN = "timespan"
    CONNECTOR = "connector"
    TRADING_PAIR = "trading_pair"
    INTEGER = "integer"
    DECIMAL = "decimal"
    STRING = "string"
    BOOLEAN = "boolean"

class ParameterGroup(str, Enum):
    GENERAL = "General Settings"
    RISK = "Risk Management"
    BUY = "Buy Order Settings"
    SELL = "Sell Order Settings"
    DCA = "DCA Settings"
    INDICATORS = "Indicator Settings"
    PROFITABILITY = "Profitability Settings"
    EXECUTION = "Execution Settings"
    ARBITRAGE = "Arbitrage Settings"
    OTHER = "Other"

class StrategyError(Exception):
    """Base class for strategy-related errors"""

class StrategyNotFoundError(StrategyError):
    """Raised when a strategy cannot be found"""

class StrategyValidationError(StrategyError):
    """Raised when strategy parameters are invalid"""

class ParameterConstraints(BaseModel):
    min_value: Optional[Union[int, float, Decimal]] = None
    max_value: Optional[Union[int, float, Decimal]] = None
    valid_values: Optional[List[Any]] = None

class StrategyParameter(BaseModel):
    # Core attributes
    name: str
    type: str
    required: bool
    default: Optional[Any]
    
    # Display attributes
    display_name: str
    description: str
    group: ParameterGroup
    is_advanced: bool
    
    # Validation attributes
    constraints: Optional[ParameterConstraints] = None
    
    # UI attributes
    display_type: DisplayType = DisplayType.INPUT
    
    # Type flags (for backward compatibility and specific handling)
    parameter_type: Optional[ParameterType] = None

class StrategyMapping(BaseModel):
    """Maps a strategy ID to its implementation details"""
    id: str  # e.g., "supertrend_v1"
    config_class: str  # e.g., "supertrendconfig"
    module_path: str  # e.g., "bots.controllers.directional_trading.supertrend_v1"
    strategy_type: StrategyType
    display_name: str  # e.g., "Supertrend V1"
    description: str = ""
    parameters: Dict[str, StrategyParameter] = {}

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

class StrategyRegistry:
    """Central registry for all trading strategies"""
    
    _cache: Dict[str, StrategyMapping] = {}
    
    @classmethod
    def _ensure_cache_loaded(cls):
        if not cls._cache:
            cls._cache = discover_strategies()
    
    @classmethod
    def get_all_strategies(cls) -> Dict[str, StrategyMapping]:
        """Get all available strategies with their configurations"""
        cls._ensure_cache_loaded()
        return cls._cache
    
    @classmethod
    def get_strategy(cls, strategy_id: str) -> Optional[StrategyMapping]:
        """Get a specific strategy by ID"""
        cls._ensure_cache_loaded()
        strategy = cls._cache.get(strategy_id)
        if not strategy:
            raise StrategyNotFoundError(f"Strategy '{strategy_id}' not found")
        return strategy
    
    @classmethod
    def get_strategies_by_type(cls, strategy_type: StrategyType) -> List[StrategyMapping]:
        """Get all strategies of a specific type"""
        cls._ensure_cache_loaded()
        return [s for s in cls._cache.values() if s.strategy_type == strategy_type]

def convert_to_strategy_parameter(name: str, field: ModelField) -> StrategyParameter:
    """Convert a model field to a strategy parameter"""
    constraints = ParameterConstraints()
    
    # Handle constraints
    if hasattr(field.field_info, 'ge'):
        constraints.min_value = field.field_info.ge
    elif hasattr(field.field_info, 'gt'):
        constraints.min_value = field.field_info.gt + (1 if isinstance(field.field_info.gt, int) else Decimal('0'))

    if hasattr(field.field_info, 'le'):
        constraints.max_value = field.field_info.le
    elif hasattr(field.field_info, 'lt'):
        constraints.max_value = field.field_info.lt - (1 if isinstance(field.field_info.lt, int) else Decimal('0'))

    # Determine parameter type
    param_type = None
    if "connector" in name.lower():
        param_type = ParameterType.CONNECTOR
    elif "trading_pair" in name.lower():
        param_type = ParameterType.TRADING_PAIR
    elif any(word in name.lower() for word in ["percentage", "percent", "ratio", "pct"]):
        param_type = ParameterType.PERCENTAGE
    elif "price" in name.lower():
        param_type = ParameterType.PRICE
    elif any(word in name.lower() for word in ["time", "interval", "duration"]):
        param_type = ParameterType.TIMESPAN
    elif str(field.type_.__name__).lower() == "int":
        param_type = ParameterType.INTEGER
    elif str(field.type_.__name__).lower() == "decimal":
        param_type = ParameterType.DECIMAL
    elif str(field.type_.__name__).lower() == "bool":
        param_type = ParameterType.BOOLEAN
    else:
        param_type = ParameterType.STRING

    # Determine display type
    display_type = DisplayType.INPUT
    if constraints.min_value is not None and constraints.max_value is not None:
        display_type = DisplayType.SLIDER
    elif param_type == ParameterType.BOOLEAN:
        display_type = DisplayType.TOGGLE
    elif constraints.valid_values:
        display_type = DisplayType.DROPDOWN

    # Get group
    group = determine_parameter_group(name)
    
    return StrategyParameter(
        name=name,
        type=str(field.type_.__name__),
        required=field.required or field.default is not None,
        default=field.default,
        display_name=name.replace('_', ' ').title(),
        description=field.description if hasattr(field, 'description') else "",
        group=group,
        is_advanced=is_advanced_parameter(name),
        constraints=constraints,
        display_type=display_type,
        parameter_type=param_type
    )

def determine_parameter_group(name: str) -> ParameterGroup:
    """Determine the parameter group based on the parameter name"""
    name_lower = name.lower()
    
    if any(word in name_lower for word in ["controller_name", "candles", "interval"]):
        return ParameterGroup.GENERAL
    elif any(word in name_lower for word in ["stop_loss", "trailing_stop", "take_profit", "activation_bounds", "leverage", "triple_barrier"]):
        return ParameterGroup.RISK
    elif "buy" in name_lower:
        return ParameterGroup.BUY
    elif "sell" in name_lower:
        return ParameterGroup.SELL
    elif "dca" in name_lower:
        return ParameterGroup.DCA
    elif any(word in name_lower for word in ["bb", "macd", "natr", "length", "multiplier"]):
        return ParameterGroup.INDICATORS
    elif any(word in name_lower for word in ["profitability", "position_size"]):
        return ParameterGroup.PROFITABILITY
    elif any(word in name_lower for word in ["time_limit", "executor", "imbalance"]):
        return ParameterGroup.EXECUTION
    elif any(word in name_lower for word in ["spot", "perp"]):
        return ParameterGroup.ARBITRAGE
    else:
        return ParameterGroup.OTHER

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
def discover_strategies() -> Dict[str, StrategyMapping]:
    """Discover and load all available strategies"""
    strategies = {}
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

                            # Extract strategy ID from module path
                            strategy_id = module_path.split(".")[-1]
                            
                            # Get strategy type
                            strategy_type = infer_strategy_type(module_path, obj)
                            
                            # Get display info
                            display_info = get_strategy_display_info().get(strategy_id, {})
                            
                            # Convert parameters
                            parameters = {}
                            for field_name, field in obj.__fields__.items():
                                param = convert_to_strategy_parameter(field_name, field)
                                parameters[field_name] = param
                            
                            # Create strategy
                            strategies[strategy_id] = StrategyMapping(
                                id=strategy_id,
                                display_name=display_info.get("pretty_name", " ".join(word.capitalize() for word in strategy_id.split("_"))),
                                description=display_info.get("description", obj.__doc__ or ""),
                                strategy_type=strategy_type,
                                module_path=module_path,
                                config_class=obj.__name__,
                                parameters=parameters
                            )

                except ImportError as e:
                    logger.error(f"Error importing module {module_path}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error processing {module_path}: {e}")
                    import traceback
                    traceback.print_exc()

    return strategies

def get_strategy_mapping(strategy_id: str) -> Optional[StrategyMapping]:
    """
    DEPRECATED: Use StrategyRegistry.get_strategy() instead
    Get strategy mapping by ID
    """
    logger.warning("get_strategy_mapping is deprecated. Use StrategyRegistry.get_strategy() instead")
    strategy = StrategyRegistry.get_strategy(strategy_id)
    if not strategy:
        return None
    return StrategyMapping(
        id=strategy.id,
        config_class=strategy.config_class,
        module_path=strategy.module_path,
        strategy_type=strategy.type,
        display_name=strategy.name,
        description=strategy.description
    )

def get_strategy_module_path(strategy_id: str) -> Optional[str]:
    """
    DEPRECATED: Use StrategyRegistry.get_strategy().module_path instead
    Get the module path for a strategy
    """
    logger.warning("get_strategy_module_path is deprecated. Use StrategyRegistry.get_strategy().module_path instead")
    strategy = StrategyRegistry.get_strategy(strategy_id)
    return strategy.module_path if strategy else None

def is_advanced_parameter(name: str) -> bool:
    """Determine if a parameter should be considered advanced"""
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
