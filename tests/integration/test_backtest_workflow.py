import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from trading.data_sources.birdeye_order_book import BirdeyeOrderBookDataSource
from trading.data_sources.birdeye_ohlcv import BirdeyeOHLCVDataSource

class MockBirdeyeService:
    def __init__(self, mock_responses):
        self._mock_responses = mock_responses
        self.base_url = "https://public-api.birdeye.so"
        self.api_key = ""
    
    async def get_historical_data(self, token_address: str, start_time: int, end_time: int, resolution: str = "15"):
        # Return mock data regardless of API key
        start_dt = datetime.fromtimestamp(start_time)
        end_dt = datetime.fromtimestamp(end_time)
        interval_minutes = int(resolution)
        
        # Use the provided mock data
        return self._mock_responses["ohlcv"]["data"]["items"]
    
    async def get_price(self, token_address: str):
        return float(self._mock_responses["price"]["data"]["value"])
    
    async def get_token_info(self, token_address: str):
        return {
            "address": token_address,
            "symbol": "TEST",
            "name": "Test Token",
            "decimals": 9,
            "logoURI": "",
            "coingeckoId": "test-token"
        }

@pytest.mark.asyncio
async def test_backtest_workflow(client: TestClient):
    """Test the backtest workflow API endpoint."""
    # Test data
    start_time = int(datetime(2023, 1, 1).timestamp())
    end_time = int((datetime(2023, 1, 1) + timedelta(days=1)).timestamp())
    
    # Use BONK token address for testing
    bonk_token_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    
    # Mock OHLCV data
    mock_candles = {
        "data": {
            "items": [
                {
                    "unixTime": start_time,
                    "o": "0.000012",
                    "h": "0.000013",
                    "l": "0.000011",
                    "c": "0.000012",
                    "v": "1000000"
                },
                {
                    "unixTime": start_time + 3600,
                    "o": "0.000012",
                    "h": "0.000014",
                    "l": "0.000012",
                    "c": "0.000013",
                    "v": "1500000"
                }
            ]
        }
    }
    
    # Mock order book data
    mock_orderbook = {
        "bids": [[0.000012, 1000000], [0.000011, 2000000]],
        "asks": [[0.000013, 1500000], [0.000014, 2500000]]
    }
    
    backtest_request = {
        "module_path": "bots.controllers.directional_trading.bollinger_v1",
        "strategy_name": "BollingerV1Controller",
        "start_time": start_time,
        "end_time": end_time,
        "exchange": "birdeye",
        "trading_pair": bonk_token_address,
        "leverage": 1,
        "parameters": {
            # Base controller fields
            "controller_name": "bollinger_v1",
            "connector_name": "birdeye",
            "trading_pair": bonk_token_address,
            "max_executors_per_side": 2,
            "cooldown_time": 300,
            "leverage": 1,
            "position_mode": "ONEWAY",
            "stop_loss": "0.03",
            "take_profit": "0.02",
            "time_limit": 2700,
            "take_profit_order_type": "LIMIT",
            "trailing_stop": "0.015,0.003",
            
            # Bollinger specific fields
            "interval": "30m",
            "bb_length": 100,
            "bb_std": 2.0,
            "bb_long_threshold": 0.0,
            "bb_short_threshold": 1.0,
            "candles_config": [],
            "candles_connector": "birdeye",
            "candles_trading_pair": bonk_token_address
        }
    }

    # Set up mock responses
    mock_responses = {
        "ohlcv": mock_candles,
        "orderbook": mock_orderbook,
        "price": {"data": {"value": "0.000012"}}
    }
    
    # Create mock service
    mock_service = MockBirdeyeService(mock_responses)
    
    # Patch both the service and the data provider
    with patch('services.birdeye_service.BirdeyeService', return_value=mock_service):
        try:
            # Run backtest
            response = client.post("/api/v1/backtest", json=backtest_request)
            assert response.status_code == 200, f"Response: {response.json()}"

            # Verify response structure
            data = response.json()
            assert "results" in data
            results = data["results"]
            
            # Verify required fields
            assert "total_pnl" in results
            assert "total_trades" in results
            assert "win_rate" in results
            assert "profit_loss_ratio" in results
            assert "max_drawdown" in results
            assert "trades" in results
            
            # Verify trades structure
            trades = results["trades"]
            assert isinstance(trades, list)
            if trades:
                trade = trades[0]
                assert "entry_time" in trade
                assert "exit_time" in trade
                assert "trading_pair" in trade
                assert "side" in trade
                assert "entry_price" in trade
                assert "exit_price" in trade
                assert "amount" in trade
                assert "pnl" in trade
                assert "pnl_pct" in trade
                assert "fee" in trade
                assert "status" in trade
        
        finally:
            # Allow any pending tasks to complete
            await asyncio.sleep(0)
    