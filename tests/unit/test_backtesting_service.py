import pytest
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

from services.backtesting_service import (
    BacktestingService,
    BacktestError
)
from routers.backtest_models import BacktestingConfig, BacktestResponse
from routers.strategies_models import (
    StrategyRegistry,
    StrategyNotFoundError,
    StrategyType,
    StrategyMapping,
    StrategyParameter,
    ParameterGroup,
    DisplayType,
    StrategyConfig
)

@pytest.fixture
def mock_strategy_registry(monkeypatch):
    """Mock strategy registry for testing"""
    strategy = StrategyMapping(
        id="bollinger_v1",
        config_class="BollingerV1ControllerConfig",
        module_path="bots.controllers.directional_trading.bollinger_v1",
        strategy_type=StrategyType.DIRECTIONAL_TRADING,
        display_name="Bollinger Bands Strategy",
        description="A strategy that uses Bollinger Bands for trading decisions",
        parameters={
            "bb_length": StrategyParameter(
                name="bb_length",
                type="int",
                required=True,
                default=100,
                display_name="BB Length",
                description="Length of the Bollinger Bands period",
                group=ParameterGroup.INDICATORS,
                is_advanced=False,
                display_type=DisplayType.INPUT
            ),
            "bb_std": StrategyParameter(
                name="bb_std",
                type="float",
                required=True,
                default=2.0,
                display_name="BB Standard Deviation",
                description="Number of standard deviations for the bands",
                group=ParameterGroup.INDICATORS,
                is_advanced=False,
                display_type=DisplayType.INPUT
            )
        }
    )
    
    def mock_get_strategy(strategy_id: str) -> StrategyMapping:
        if strategy_id != "bollinger_v1":
            raise StrategyNotFoundError(f"Strategy {strategy_id} not found")
        return strategy
    
    monkeypatch.setattr(StrategyRegistry, "get_strategy", mock_get_strategy)
    return strategy

@pytest.fixture
def backtesting_service():
    """Create a backtesting service instance for testing"""
    return BacktestingService()

@pytest.mark.asyncio
async def test_validate_time_range(backtesting_service):
    """Test time range validation"""
    # Valid time range
    backtesting_service.validate_time_range(1000, 2000)
    
    # Invalid time range
    with pytest.raises(BacktestError, match="Invalid time range"):
        backtesting_service.validate_time_range(2000, 1000)

@pytest.mark.asyncio
async def test_transform_strategy_config_success(backtesting_service, mock_strategy_registry):
    """Test successful strategy config transformation"""
    config = {
        "strategy_id": "bollinger_v1",
        "bb_length": 100,
        "bb_std": 2.0
    }
    
    result = backtesting_service.transform_strategy_config(config)
    
    assert result["controller_type"] == StrategyType.DIRECTIONAL_TRADING.value
    assert result["controller_name"] == "bollinger_v1"
    assert result["bb_length"] == 100
    assert result["bb_std"] == 2.0

@pytest.mark.asyncio
async def test_transform_strategy_config_missing_id(backtesting_service):
    """Test strategy config transformation with missing ID"""
    config = {
        "bb_length": 100,
        "bb_std": 2.0
    }
    
    with pytest.raises(BacktestError, match="Missing strategy_id"):
        backtesting_service.transform_strategy_config(config)

@pytest.mark.asyncio
async def test_transform_strategy_config_not_found(backtesting_service, mock_strategy_registry):
    """Test strategy config transformation with non-existent strategy"""
    config = {
        "strategy_id": "nonexistent_strategy",
        "bb_length": 100,
        "bb_std": 2.0
    }
    
    with pytest.raises(BacktestError, match="Strategy not found"):
        backtesting_service.transform_strategy_config(config)

@pytest.mark.asyncio
async def test_run_backtesting_success(backtesting_service, mock_strategy_registry):
    """Test successful backtesting run"""
    config = BacktestingConfig(
        start_time=1000,
        end_time=2000,
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "strategy_id": "bollinger_v1",
            "bb_length": 100,
            "bb_std": 2.0
        }
    )
    
    # Mock the backtesting engine
    mock_engine = AsyncMock()
    mock_engine.run_backtesting.return_value = {
        "executors": [],
        "processed_data": {"features": {}},
        "results": {
            "total_trades": 10,
            "win_rate": 0.6,
            "total_pnl": Decimal("100.0"),
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.1,
            "profit_loss_ratio": 2.0,
            "start_timestamp": 1000,
            "end_timestamp": 2000
        }
    }
    backtesting_service.backtesting_engines["directional_trading"] = mock_engine
    
    result = await backtesting_service.run_backtesting(config)
    
    assert isinstance(result, BacktestResponse)
    assert result.results.total_trades == 10
    assert result.results.win_rate == 0.6
    assert result.results.total_pnl == Decimal("100.0")

@pytest.mark.asyncio
async def test_run_backtesting_engine_error(backtesting_service, mock_strategy_registry):
    """Test backtesting run with engine error"""
    config = BacktestingConfig(
        start_time=1000,
        end_time=2000,
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "strategy_id": "bollinger_v1",
            "bb_length": 100,
            "bb_std": 2.0
        }
    )
    
    # Mock the backtesting engine to raise an error
    mock_engine = AsyncMock()
    mock_engine.run_backtesting.side_effect = Exception("Engine error")
    backtesting_service.backtesting_engines["directional_trading"] = mock_engine
    
    with pytest.raises(BacktestError, match="Error during backtesting execution"):
        await backtesting_service.run_backtesting(config)

def test_get_available_engines(backtesting_service):
    """Test getting available backtesting engines"""
    engines = backtesting_service.get_available_engines()
    
    assert isinstance(engines, dict)
    assert "directional_trading" in engines
    assert "market_making" in engines 