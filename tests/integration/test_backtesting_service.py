import pytest
from decimal import Decimal
from typing import Dict, Any
from services.backtesting_service import BacktestingService, BacktestConfigError
from routers.strategies_models import (
    StrategyMapping,
    StrategyType,
    StrategyParameter,
    ParameterConstraints,
    ParameterGroup,
    DisplayType
)
from routers.backtest_models import BacktestingConfig, BacktestResponse

@pytest.fixture
def backtesting_service():
    """Create a real backtesting service instance for integration tests"""
    return BacktestingService()

@pytest.fixture
def valid_backtest_config():
    """Valid backtest configuration for integration tests"""
    return BacktestingConfig(
        start_time=1735457150,  # Use a recent timestamp
        end_time=1735460750,    # 1 hour after start_time
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "strategy_id": "bollinger_v1",
            "bb_length": 100,
            "bb_std": 2.0,
            "bb_long_threshold": 0.0,
            "bb_short_threshold": 1.0,
            "trading_pair": "BTC-USDT",
            "leverage": 1,
            "interval": "1m"
        }
    )

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_backtesting_workflow(backtesting_service, valid_backtest_config):
    """Test the complete backtesting workflow with real dependencies"""
    response = await backtesting_service.run_backtesting(valid_backtest_config)
    
    # Verify response structure
    assert isinstance(response, BacktestResponse)
    assert response.processed_data is not None
    assert response.results is not None
    
    # Verify processed data
    assert isinstance(response.processed_data.features, dict)
    assert len(response.processed_data.features) > 0
    
    # Verify executors
    assert isinstance(response.executors, list)
    if response.executors:
        executor = response.executors[0]
        assert executor.level_id is not None
        assert executor.timestamp is not None
        assert executor.connector_name is not None
        assert executor.trading_pair is not None
        assert isinstance(executor.entry_price, Decimal)
        assert isinstance(executor.amount, Decimal)
        assert executor.side in ["BUY", "SELL"]
        assert isinstance(executor.leverage, int)
        assert executor.position_mode in ["ONEWAY", "HEDGE"]
    
    # Verify results
    assert isinstance(response.results.total_trades, int)
    assert isinstance(response.results.win_rate, float)
    assert isinstance(response.results.total_pnl, Decimal)
    assert isinstance(response.results.sharpe_ratio, float)
    assert isinstance(response.results.max_drawdown, float)
    assert isinstance(response.results.profit_loss_ratio, float)
    assert response.results.start_timestamp == valid_backtest_config.start_time
    assert response.results.end_timestamp == valid_backtest_config.end_time

@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_strategy_id(backtesting_service):
    """Test backtesting with non-existent strategy ID"""
    config = BacktestingConfig(
        start_time=1735457150,
        end_time=1735460750,
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "strategy_id": "nonexistent_strategy"
        }
    )
    
    with pytest.raises(BacktestConfigError, match="Strategy not found"):
        await backtesting_service.run_backtesting(config)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_time_range(backtesting_service):
    """Test backtesting with invalid time range"""
    config = BacktestingConfig(
        start_time=1735460750,  # End time before start time
        end_time=1735457150,
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "strategy_id": "bollinger_v1",
            "bb_length": 100,
            "bb_std": 2.0,
            "bb_long_threshold": 0.0,
            "bb_short_threshold": 1.0,
            "trading_pair": "BTC-USDT",
            "leverage": 1,
            "interval": "1m"
        }
    )
    
    with pytest.raises(BacktestConfigError, match="Invalid time range"):
        await backtesting_service.run_backtesting(config)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_required_parameters(backtesting_service):
    """Test backtesting with missing required strategy parameters"""
    config = BacktestingConfig(
        start_time=1735457150,
        end_time=1735460750,
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "strategy_id": "bollinger_v1",
            # Missing required parameters
        }
    )
    
    with pytest.raises(BacktestConfigError):
        await backtesting_service.run_backtesting(config)

@pytest.mark.integration
def test_get_available_engines_integration(backtesting_service):
    """Test getting available backtesting engines"""
    engines = backtesting_service.get_available_engines()
    
    assert isinstance(engines, dict)
    assert len(engines) > 0
    assert "directional_trading" in engines
    assert "market_making" in engines

@pytest.mark.integration
def test_get_engine_config_schema_integration(backtesting_service):
    """Test getting engine configuration schema"""
    schema = backtesting_service.get_engine_config_schema("directional_trading")
    
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "strategy_id" in schema["properties"]
    assert "trading_pair" in schema["properties"]
    assert "leverage" in schema["properties"]
    assert "interval" in schema["properties"]
    assert "stop_loss" in schema["properties"]
    assert "take_profit" in schema["properties"]
    assert "required" in schema
    assert "strategy_id" in schema["required"]
    assert "trading_pair" in schema["required"] 