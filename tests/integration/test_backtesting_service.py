import pytest
from decimal import Decimal
from typing import Dict, Any
from datetime import datetime, timedelta
from services.backtesting_service import BacktestingService, BacktestError
from routers.strategies_models import (
    StrategyMapping,
    StrategyType,
    StrategyParameter,
    ParameterConstraints,
    ParameterGroup,
    DisplayType, StrategyNotFoundError
)
from routers.backtest_models import BacktestingConfig, BacktestResponse

@pytest.fixture
def backtesting_service():
    """Create a real backtesting service instance for integration tests"""
    return BacktestingService()

@pytest.fixture
def recent_timestamps():
    """Get recent timestamps for testing"""
    now = datetime.now()
    start = now - timedelta(hours=1)
    return {
        "start": int(start.timestamp()),
        "end": int(now.timestamp())
    }

@pytest.fixture
def bollinger_config(recent_timestamps):
    """Valid Bollinger Bands strategy configuration"""
    return BacktestingConfig(
        start_time=recent_timestamps["start"],
        end_time=recent_timestamps["end"],
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "controller_name": "bollinger_v1",
            "bb_length": 100,
            "bb_std": 2.0,
            "bb_long_threshold": 0.0,
            "bb_short_threshold": 1.0,
            "trading_pair": "BTC-USDT",
            "leverage": 1,
            "interval": "1m",
            "stop_loss": 0.03,
            "take_profit": 0.02,
            "connector_name": "binance_perpetual",
            "candles_connector": "binance_perpetual",
            "candles_trading_pair": "BTC-USDT"
        }
    )

@pytest.fixture
def pmm_config(recent_timestamps):
    """Valid Pure Market Making strategy configuration"""
    return BacktestingConfig(
        start_time=recent_timestamps["start"],
        end_time=recent_timestamps["end"],
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "controller_name": "pmm_simple",
            "trading_pair": "BTC-USDT",
            "leverage": 1,
            "interval": "1m",
            "bid_spread": 0.002,
            "ask_spread": 0.002,
            "order_amount": 0.01,
            "order_refresh_time": 60,
            "max_order_age": 1800,
            "connector_name": "binance_perpetual",
            "candles_connector": "binance_perpetual",
            "candles_trading_pair": "BTC-USDT"
        }
    )

@pytest.mark.integration
@pytest.mark.asyncio
async def test_directional_trading_workflow(backtesting_service, bollinger_config):
    """Test complete backtesting workflow with Bollinger Bands strategy"""
    response = await backtesting_service.run_backtesting(bollinger_config)
    
    # Verify response structure
    assert isinstance(response, BacktestResponse)
    assert response.processed_data is not None
    assert response.results is not None
    
    # Verify processed data contains required features
    features = response.processed_data.features
    assert isinstance(features, dict)
    assert len(features) > 0
    assert "BBL_100_2.0" in features  # Lower Bollinger Band
    assert "BBM_100_2.0" in features  # Middle Bollinger Band
    assert "BBU_100_2.0" in features  # Upper Bollinger Band
    assert "BBP_100_2.0" in features  # Bollinger Band Position
    
    # Verify executors
    assert isinstance(response.executors, list)
    if response.executors:
        executor = response.executors[0]
        assert executor.level_id is not None
        assert executor.timestamp is not None
        assert executor.connector_name is not None
        assert executor.trading_pair == "BTC-USDT"
        assert isinstance(executor.entry_price, Decimal)
        assert isinstance(executor.amount, Decimal)
        assert executor.side in ["BUY", "SELL"]
        assert executor.leverage == 1
        assert executor.position_mode == "ONEWAY"
    
    # Verify results
    results = response.results
    assert isinstance(results.total_trades, int)
    assert isinstance(results.win_rate, float)
    assert isinstance(results.total_pnl, Decimal)
    assert isinstance(results.sharpe_ratio, float)
    assert isinstance(results.max_drawdown, float)
    assert isinstance(results.profit_loss_ratio, float)
    assert results.start_timestamp == bollinger_config.start_time
    assert results.end_timestamp == bollinger_config.end_time
    assert results.win_rate >= 0 and results.win_rate <= 1
    assert results.max_drawdown >= 0 and results.max_drawdown <= 1

@pytest.mark.integration
@pytest.mark.asyncio
async def test_market_making_workflow(backtesting_service, pmm_config):
    """Test complete backtesting workflow with Pure Market Making strategy"""
    response = await backtesting_service.run_backtesting(pmm_config)
    
    # Verify response structure
    assert isinstance(response, BacktestResponse)
    assert response.processed_data is not None
    assert response.results is not None
    
    # Verify processed data contains required features
    features = response.processed_data.features
    assert isinstance(features, dict)
    assert len(features) > 0
    assert "price" in features
    assert "volume" in features
    
    # Verify executors
    assert isinstance(response.executors, list)
    if response.executors:
        executor = response.executors[0]
        assert executor.level_id is not None
        assert executor.timestamp is not None
        assert executor.connector_name is not None
        assert executor.trading_pair == "BTC-USDT"
        assert isinstance(executor.entry_price, Decimal)
        assert isinstance(executor.amount, Decimal)
        assert executor.side in ["BUY", "SELL"]
        assert executor.leverage == 1
        assert executor.position_mode == "ONEWAY"
    
    # Verify results
    results = response.results
    assert isinstance(results.total_trades, int)
    assert isinstance(results.win_rate, float)
    assert isinstance(results.total_pnl, Decimal)
    assert isinstance(results.sharpe_ratio, float)
    assert isinstance(results.max_drawdown, float)
    assert isinstance(results.profit_loss_ratio, float)
    assert results.start_timestamp == pmm_config.start_time
    assert results.end_timestamp == pmm_config.end_time
    assert results.win_rate >= 0 and results.win_rate <= 1
    assert results.max_drawdown >= 0 and results.max_drawdown <= 1

@pytest.mark.integration
@pytest.mark.asyncio
async def test_different_time_ranges(backtesting_service, bollinger_config):
    """Test backtesting with different time ranges and resolutions"""
    # Test with 1-hour data
    bollinger_config.backtesting_resolution = "1h"
    bollinger_config.config["interval"] = "1h"
    response = await backtesting_service.run_backtesting(bollinger_config)
    assert response.results.end_timestamp - response.results.start_timestamp == bollinger_config.end_time - bollinger_config.start_time
    
    # Test with 15-minute data
    bollinger_config.backtesting_resolution = "15m"
    bollinger_config.config["interval"] = "15m"
    response = await backtesting_service.run_backtesting(bollinger_config)
    assert response.results.end_timestamp - response.results.start_timestamp == bollinger_config.end_time - bollinger_config.start_time

@pytest.mark.integration
@pytest.mark.asyncio
async def test_parameter_validation(backtesting_service, bollinger_config):
    """Test parameter validation for strategy configurations"""
    # Test invalid BB length
    invalid_config = bollinger_config.copy()
    invalid_config.config["bb_length"] = 0
    with pytest.raises(BacktestError, match="Invalid parameter"):
        await backtesting_service.run_backtesting(invalid_config)
    
    # Test invalid BB std
    invalid_config = bollinger_config.copy()
    invalid_config.config["bb_std"] = -1.0
    with pytest.raises(BacktestError, match="Invalid parameter"):
        await backtesting_service.run_backtesting(invalid_config)
    
    # Test invalid leverage
    invalid_config = bollinger_config.copy()
    invalid_config.config["leverage"] = 0
    with pytest.raises(BacktestError, match="Invalid parameter"):
        await backtesting_service.run_backtesting(invalid_config)
    
    # Test invalid trading pair format
    invalid_config = bollinger_config.copy()
    invalid_config.config["trading_pair"] = "BTCUSDT"  # Missing hyphen
    with pytest.raises(BacktestError, match="Invalid trading pair format"):
        await backtesting_service.run_backtesting(invalid_config)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_controller_name(backtesting_service, recent_timestamps):
    """Test backtesting with non-existent strategy ID"""
    config = BacktestingConfig(
        start_time=recent_timestamps["start"],
        end_time=recent_timestamps["end"],
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "controller_name": "nonexistent_strategy"
        }
    )
    
    with pytest.raises(StrategyNotFoundError, match="Strategy not found"):
        await backtesting_service.run_backtesting(config)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_time_range(backtesting_service, recent_timestamps):
    """Test backtesting with invalid time range"""
    config = BacktestingConfig(
        start_time=recent_timestamps["end"],
        end_time=recent_timestamps["start"],
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "controller_name": "bollinger_v1",
            "bb_length": 100,
            "bb_std": 2.0,
            "bb_long_threshold": 0.0,
            "bb_short_threshold": 1.0,
            "trading_pair": "BTC-USDT",
            "leverage": 1,
            "interval": "1m"
        }
    )
    
    with pytest.raises(BacktestError, match="Invalid time range"):
        await backtesting_service.run_backtesting(config)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_required_parameters(backtesting_service, recent_timestamps):
    """Test backtesting with missing required strategy parameters"""
    config = BacktestingConfig(
        start_time=recent_timestamps["start"],
        end_time=recent_timestamps["end"],
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "controller_name": "bollinger_v1",
            # Missing required parameters
        }
    )
    
    with pytest.raises(BacktestError):
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
    # Test directional trading schema
    dt_schema = backtesting_service.get_engine_config_schema("directional_trading")
    assert isinstance(dt_schema, dict)
    assert dt_schema["type"] == "object"
    assert "properties" in dt_schema
    assert "controller_name" in dt_schema["properties"]
    assert "trading_pair" in dt_schema["properties"]
    assert "leverage" in dt_schema["properties"]
    assert "interval" in dt_schema["properties"]
    assert "stop_loss" in dt_schema["properties"]
    assert "take_profit" in dt_schema["properties"]
    assert "required" in dt_schema
    print(dt_schema["required"])
    assert "trading_pair" in dt_schema["required"]
    
    # Test market making schema
    mm_schema = backtesting_service.get_engine_config_schema("market_making")
    assert isinstance(mm_schema, dict)
    assert mm_schema["type"] == "object"
    assert "properties" in mm_schema
    assert "trading_pair" in mm_schema["properties"]
    assert "bid_spread" in mm_schema["properties"]
    assert "ask_spread" in mm_schema["properties"]
    assert "order_amount" in mm_schema["properties"]
    assert "required" in mm_schema
    assert "trading_pair" in mm_schema["required"] 