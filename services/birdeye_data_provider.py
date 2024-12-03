import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from hummingbot.core.data_type.common import PriceType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from services.birdeye_service import BirdeyeService

class BirdeyeDataProvider(MarketDataProvider):
    """A custom data provider that uses Birdeye historical data."""
    
    def __init__(self):
        super().__init__({})  # No connectors needed
        self._candles_data: Dict[str, pd.DataFrame] = {}
        self._birdeye_service = BirdeyeService()
        
    async def get_candles_df(
        self,
        connector_name: str,
        trading_pair: str,
        interval: str,
        max_records: Optional[int] = None
    ) -> pd.DataFrame:
        """Get candles data for a specific trading pair."""
        key = f"{connector_name}_{trading_pair}_{interval}"
        if key not in self._candles_data:
            # Fetch data from Birdeye
            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)  # Get 30 days of data
            
            # Convert interval to resolution
            resolution = self._convert_interval_to_resolution(interval)
            
            # Get historical data from Birdeye
            data = await self._birdeye_service.get_historical_data(
                token_address=trading_pair,
                start_time=int(start_time.timestamp()),
                end_time=int(end_time.timestamp()),
                resolution=resolution
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            df.set_index("timestamp", inplace=True)
            
            self._candles_data[key] = df
        
        df = self._candles_data[key]
        if max_records is not None:
            df = df.tail(max_records)
        
        return df
    
    def add_candles_data(
        self,
        connector_name: str,
        trading_pair: str,
        interval: str,
        data: pd.DataFrame
    ) -> None:
        """Add candles data for a specific trading pair."""
        key = f"{connector_name}_{trading_pair}_{interval}"
        self._candles_data[key] = data
    
    async def get_price(
        self,
        connector_name: str,
        trading_pair: str,
        price_type: PriceType = PriceType.MidPrice
    ) -> Decimal:
        """Get current price for a trading pair."""
        # Get current price from Birdeye
        price = await self._birdeye_service.get_price(trading_pair)
        return Decimal(str(price))
    
    def _convert_interval_to_resolution(self, interval: str) -> str:
        """Convert Hummingbot interval to Birdeye resolution."""
        # Convert interval like "1m", "5m", "1h" to resolution like "1", "5", "60"
        unit = interval[-1]
        value = int(interval[:-1])
        
        if unit == "m":
            return str(value)
        elif unit == "h":
            return str(value * 60)
        elif unit == "d":
            return str(value * 1440)
        else:
            return "1"  # Default to 1 minute