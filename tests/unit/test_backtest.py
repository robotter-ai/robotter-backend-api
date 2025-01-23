import json
from pathlib import Path

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
import pandas as pd

from routers.backtest import (
    run_backtesting,
    get_available_engines,
    get_engine_config_schema,
)
from routers.backtest_models import BacktestResponse, BacktestResults, BacktestingConfig, ExecutorInfo, ProcessedData
from services.backtesting_service import (
    BacktestConfigError,
    BacktestEngineError,
)
from routers.strategies_models import (
    StrategyType,
    StrategyMapping,
    StrategyConfig,
    StrategyParameter,
    ParameterGroup,
)

# Load test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(filename: str) -> dict:
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)

MOCK_STRATEGY_CONFIG = load_fixture("strategy_config.json")
MOCK_BACKTEST_RESULTS = load_fixture("backtest_results.json")
MOCK_MARKET_DATA = load_fixture("market_data.json")

@pytest.fixture
def mock_market_data_provider():
    """Mock the market data provider to return test data"""
    mock = Mock()
    df = pd.DataFrame(MOCK_MARKET_DATA)
    mock.get_candles_df.return_value = df
    return mock

@pytest.fixture
def mock_strategy():
    """Mock strategy configuration from registry"""
    return StrategyConfig(
        id="bollinger_v1",
        name="Bollinger Bands V1",
        description="Trading strategy based on Bollinger Bands",
        mapping=StrategyMapping(
            id="bollinger_v1",
            config_class="BollingerV1ControllerConfig",
            module_path="bots.controllers.directional_trading.bollinger_v1",
            strategy_type=StrategyType.DIRECTIONAL_TRADING,
            display_name="Bollinger Bands Strategy",
            description="Trading strategy based on Bollinger Bands"
        ),
        parameters={
            "bb_length": StrategyParameter(
                name="bb_length",
                display_name="BB Length",
                description="Length of Bollinger Bands",
                type="integer",
                default=100,
                min_value=20,
                max_value=200,
                group=ParameterGroup.INDICATORS,
                is_advanced=False,
                required=True
            ),
            "bb_std": StrategyParameter(
                name="bb_std",
                display_name="BB Standard Deviation",
                description="Standard deviation multiplier",
                type="float",
                default=2.0,
                min_value=1.0,
                max_value=3.0,
                group=ParameterGroup.INDICATORS,
                is_advanced=False,
                required=True
            ),
            "bb_long_threshold": StrategyParameter(
                name="bb_long_threshold",
                display_name="BB Long Threshold",
                description="Long entry threshold",
                type="float",
                default=0.0,
                min_value=0.0,
                max_value=1.0,
                group=ParameterGroup.INDICATORS,
                is_advanced=False,
                required=True
            ),
            "bb_short_threshold": StrategyParameter(
                name="bb_short_threshold",
                display_name="BB Short Threshold",
                description="Short entry threshold",
                type="float",
                default=1.0,
                min_value=0.0,
                max_value=1.0,
                group=ParameterGroup.INDICATORS,
                is_advanced=False,
                required=True
            )
        }
    )

@pytest.fixture
def mock_registry(mock_strategy):
    """Mock strategy registry"""
    with patch("services.backtesting_service.StrategyRegistry") as mock_registry:
        mock_registry.get_strategy.return_value = mock_strategy
        yield mock_registry

@pytest.fixture
def mock_backtesting_service(mock_registry):
    """Mock backtesting service"""
    with patch("routers.backtest.backtesting_service") as mock_service:
        mock_response = BacktestResponse(
            executors=[
                ExecutorInfo(
                    id="executor_1",
                    level_id="level_1",
                    timestamp=1735457150,
                    connector_name="binance",
                    trading_pair="BTC-USDT",
                    entry_price=50000.0,
                    amount=0.1,
                    side="BUY",
                    leverage=1,
                    position_mode="ONEWAY",
                    trades=10,
                    win_rate=0.6,
                    profit_loss=150.25
                )
            ],
            processed_data=ProcessedData(
                features={
                    "price": [50100.0, 50200.0, 50300.0],
                    "volume": [10.5, 12.3, 8.7],
                    "BBL_100_2.0": [49800.0, 49900.0, 50000.0],
                    "BBM_100_2.0": [50000.0, 50100.0, 50200.0],
                    "BBU_100_2.0": [50200.0, 50300.0, 50400.0],
                    "BBP_100_2.0": [0.75, 0.80, 0.85]
                }
            ),
            results=BacktestResults(
                total_trades=10,
                win_rate=0.6,
                total_pnl=150.25,
                sharpe_ratio=1.5,
                profit_loss_ratio=1.5,
                max_drawdown=0.05,
                start_timestamp=1735457150,
                end_timestamp=1735457450
            )
        )
        mock_service.run_backtesting = AsyncMock()
        mock_service.run_backtesting.return_value = mock_response
        yield mock_service

@pytest.fixture
def valid_backtest_config():
    """Valid backtest configuration"""
    return BacktestingConfig(
        start_time=1735458769,
        end_time=1735462369,
        backtesting_resolution="1m",
        trade_cost=0.001,
        config={
            "strategy_id": "bollinger_v1",
            "trading_pair": "BTC-USDT",
            "leverage": 1,
            "bb_length": 100,
            "bb_std": 2.0,
            "bb_long_threshold": 0.0,
            "bb_short_threshold": 1.0,
            "interval": "1m"
        }
    )

# Unit Tests

@pytest.mark.asyncio
async def test_successful_backtest(valid_backtest_config, mock_backtesting_service):
    """Test successful backtesting execution and results processing"""
    response = await run_backtesting(valid_backtest_config)
    
    assert isinstance(response, BacktestResponse)
    assert len(response.executors) == 1
    assert response.executors[0].trades == 10
    assert response.executors[0].win_rate == 0.6
    assert response.executors[0].profit_loss == 150.25
    
    assert isinstance(response.processed_data, ProcessedData)
    assert "price" in response.processed_data.features
    assert "volume" in response.processed_data.features
    assert "BBL_100_2.0" in response.processed_data.features
    
    assert isinstance(response.results, BacktestResults)
    assert response.results.total_trades == 10
    assert response.results.win_rate == 0.6
    assert response.results.total_pnl == 150.25
    assert response.results.sharpe_ratio == 1.5
    assert response.results.profit_loss_ratio == 1.5

@pytest.mark.asyncio
async def test_config_error(valid_backtest_config, mock_backtesting_service):
    """Test handling of configuration errors"""
    mock_backtesting_service.run_backtesting.side_effect = BacktestConfigError("Invalid config")
    
    with pytest.raises(HTTPException) as exc_info:
        await run_backtesting(valid_backtest_config)
    assert exc_info.value.status_code == 400
    assert str(exc_info.value.detail) == "Invalid config"

@pytest.mark.asyncio
async def test_engine_error(valid_backtest_config, mock_backtesting_service):
    """Test handling of engine errors"""
    mock_backtesting_service.run_backtesting.side_effect = BacktestEngineError("Engine error")
    
    with pytest.raises(HTTPException) as exc_info:
        await run_backtesting(valid_backtest_config)
    assert exc_info.value.status_code == 500
    assert str(exc_info.value.detail) == "Engine error"

def test_get_available_engines(mock_backtesting_service):
    """Test getting available engines"""
    mock_backtesting_service.get_available_engines.return_value = {
        "directional_trading": "DirectionalTradingEngine",
        "market_making": "MarketMakingEngine"
    }
    engines = get_available_engines()
    assert isinstance(engines, dict)
    assert "directional_trading" in engines.keys()
    assert "market_making" in engines.keys()
    assert engines["directional_trading"] == "DirectionalTradingEngine"
    assert engines["market_making"] == "MarketMakingEngine"

def test_get_engine_config_schema(mock_backtesting_service):
    """Test getting engine configuration schema"""
    mock_backtesting_service.get_engine_config_schema.return_value = {
        "type": "object",
        "properties": {
            "stop_loss": {"type": "number"},
            "take_profit": {"type": "number"}
        }
    }
    schema = get_engine_config_schema("directional_trading")
    assert "type" in schema
    assert "properties" in schema

def test_get_engine_config_schema_not_found(mock_backtesting_service):
    """Test getting configuration schema for non-existent engine"""
    mock_backtesting_service.get_engine_config_schema.return_value = None
    
    with pytest.raises(HTTPException) as exc_info:
        get_engine_config_schema("invalid_engine")
    assert exc_info.value.status_code == 404
    assert "Engine type 'invalid_engine' not found" in str(exc_info.value.detail) 