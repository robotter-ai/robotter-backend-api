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


def convert_to_strategy_parameter(name: str, field: ModelField) -> StrategyParameter:
    param = StrategyParameter(
        name=name,
        type=str(field.type_.__name__),
        prompt=field.description if hasattr(field, 'description') else "",
        default=field.default,
        required=field.required or field.default is not None,
    )
    
    # structure of field
    print(field)
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
    
    # Check for specific use cases
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