import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from typing import Dict, Any
from pydantic import BaseModel, Field
from hummingbot.strategy_v2.controllers import ControllerConfigBase

from routers.strategies_models import (
    StrategyType,
    StrategyMapping,
    StrategyParameter,
    StrategyConfig,
    discover_strategies,
    generate_strategy_mapping,
    convert_to_strategy_parameter,
    infer_strategy_type
)

# Mock strategy config class for testing
class MockStrategyConfig(ControllerConfigBase):
    """Test strategy for unit testing"""
    controller_name = "test_strategy_v1"
    
    stop_loss: Decimal = Field(
        default=Decimal("0.03"),
        description="Stop loss percentage",
        ge=Decimal("0"),
        le=Decimal("1")
    )
    take_profit: Decimal = Field(
        default=Decimal("0.02"),
        description="Take profit percentage",
        ge=Decimal("0"),
        le=Decimal("1")
    )
    time_limit: int = Field(
        default=2700,
        description="Time limit in seconds",
        gt=0
    )
    leverage: int = Field(
        default=20,
        description="Leverage multiplier",
        gt=0
    )
    trading_pair: str = Field(
        default="BTC-USDT",
        description="Trading pair to use"
    )

# Test data
MOCK_MODULE_PATH = "bots.controllers.directional_trading.test_strategy_v1"

@pytest.fixture
def mock_strategy_config():
    return MockStrategyConfig

@pytest.fixture(autouse=True)
def mock_importlib():
    with patch("importlib.import_module") as mock:
        mock.return_value = MagicMock(
            __name__="test_module",
            MockStrategyConfig=MockStrategyConfig
        )
        yield mock

@pytest.fixture(autouse=True)
def mock_os_walk():
    with patch("os.walk") as mock:
        mock.return_value = [
            ("bots/controllers/directional_trading", [], ["test_strategy_v1.py"]),
        ]
        yield mock

@pytest.fixture(autouse=True)
def mock_discover_strategies():
    """Mock discover_strategies to return our test data"""
    with patch("routers.strategies_models.discover_strategies", autospec=True) as mock:
        mock.return_value = {
            "test_strategy_v1": StrategyConfig(
                mapping=StrategyMapping(
                    id="test_strategy_v1",
                    config_class="MockStrategyConfig",
                    module_path=MOCK_MODULE_PATH,
                    strategy_type=StrategyType.DIRECTIONAL_TRADING,
                    display_name="Test Strategy V1",
                    description="Test strategy for unit testing"
                ),
                parameters={
                    "stop_loss": StrategyParameter(
                        name="Stop Loss",
                        group="Risk Management",
                        type="Decimal",
                        prompt="Enter stop loss value",
                        default=Decimal("0.03"),
                        required=True,
                        min_value=Decimal("0"),
                        max_value=Decimal("1")
                    ),
                    "take_profit": StrategyParameter(
                        name="Take Profit",
                        group="Risk Management",
                        type="Decimal",
                        prompt="Enter take profit value",
                        default=Decimal("0.02"),
                        required=True,
                        min_value=Decimal("0"),
                        max_value=Decimal("1")
                    ),
                    "time_limit": StrategyParameter(
                        name="Time Limit",
                        group="General Settings",
                        type="int",
                        prompt="Enter time limit in seconds",
                        default=2700,
                        required=True,
                        min_value=0
                    ),
                    "leverage": StrategyParameter(
                        name="Leverage",
                        group="Risk Management",
                        type="int",
                        prompt="Enter leverage multiplier",
                        default=20,
                        required=True,
                        min_value=1,
                        is_advanced=True
                    ),
                    "trading_pair": StrategyParameter(
                        name="Trading Pair",
                        group="General Settings",
                        type="str",
                        prompt="Enter trading pair",
                        default="BTC-USDT",
                        required=True,
                        is_trading_pair=True
                    )
                }
            )
        }
        yield mock

def test_infer_strategy_type():
    """Test strategy type inference from module path"""
    assert infer_strategy_type("bots.controllers.directional_trading.test", None) == StrategyType.DIRECTIONAL_TRADING
    assert infer_strategy_type("bots.controllers.market_making.test", None) == StrategyType.MARKET_MAKING
    assert infer_strategy_type("bots.controllers.generic.test", None) == StrategyType.GENERIC

def test_generate_strategy_mapping():
    """Test strategy mapping generation"""
    mapping = generate_strategy_mapping(MOCK_MODULE_PATH, MockStrategyConfig)
    
    assert mapping.id == "test_strategy_v1"
    assert mapping.config_class == "MockStrategyConfig"
    assert mapping.module_path == MOCK_MODULE_PATH
    assert mapping.strategy_type == StrategyType.DIRECTIONAL_TRADING
    assert mapping.display_name == "Test Strategy V1"
    assert "Test strategy for unit testing" in mapping.description

def test_convert_to_strategy_parameter():
    """Test parameter conversion from config field"""
    # Get a field from the mock config
    field = MockStrategyConfig.__fields__["stop_loss"]
    param = convert_to_strategy_parameter("stop_loss", field)
    
    assert param.name == "Stop Loss"
    assert param.group == "Risk Management"
    assert param.type == "ConstrainedDecimalValue"  # We want the base type, not the constrained type
    assert param.default == Decimal("0.03")
    assert param.required is True
    assert param.min_value == Decimal("0")
    assert param.max_value == Decimal("1")
    assert param.display_type == "slider"

@pytest.mark.asyncio
async def test_discover_strategies():
    """Test strategy auto-discovery"""
    strategies = discover_strategies()
    
    assert len(strategies) == 9
    assert "bollinger_v1" in strategies
    
    strategy = strategies["bollinger_v1"]
    assert isinstance(strategy, StrategyConfig)
    assert strategy.mapping.id == "bollinger_v1"
    
    # Check some parameters
    assert "stop_loss" in strategy.parameters
    assert "take_profit" in strategy.parameters
    assert strategy.parameters["leverage"].is_advanced is True
    assert strategy.parameters["trading_pair"].is_trading_pair is True


def test_parameter_validation():
    """Test parameter validation in strategy config"""
    # Test required parameters
    with pytest.raises(ValueError):
        MockStrategyConfig(
            stop_loss=None,  # Required parameter missing
            take_profit=Decimal("0.02"),
            time_limit=2700,
            leverage=20,
            trading_pair="BTC-USDT"
        )
    
    # Test parameter constraints
    with pytest.raises(ValueError):
        MockStrategyConfig(
            stop_loss=Decimal("-0.03"),  # Negative value not allowed
            take_profit=Decimal("0.02"),
            time_limit=2700,
            leverage=20,
            trading_pair="BTC-USDT"
        )

def test_strategy_type_enum():
    """Test StrategyType enum values"""
    assert StrategyType.DIRECTIONAL_TRADING == "directional_trading"
    assert StrategyType.MARKET_MAKING == "market_making"
    assert StrategyType.GENERIC == "generic"
    
    # Test that invalid types are not allowed
    with pytest.raises(ValueError):
        StrategyType("invalid_type") 