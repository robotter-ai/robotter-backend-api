import aiohttp
from typing import List, Dict, Any
import os

class BirdeyeService:
    """Service for interacting with the Birdeye API."""
    
    def __init__(self):
        self.base_url = "https://public-api.birdeye.so"
        self.api_key = os.getenv("BIRDEYE_API_KEY", "")
        self._session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
    
    async def get_historical_data(
        self,
        token_address: str,
        start_time: int,
        end_time: int,
        resolution: str = "15"  # 15 minutes by default
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical price data from Birdeye.
        If no API key is available, returns mock data for testing.
        
        Args:
            token_address: The Solana token address
            start_time: Start timestamp in seconds
            end_time: End timestamp in seconds
            resolution: Time resolution in minutes (1, 15, 60, 240, 1D)
        
        Returns:
            List of candle data with timestamp, open, high, low, close, volume
        """
        # If API key is available, use the real API
        url = f"{self.base_url}/public/history_price"
        headers = {"X-API-KEY": self.api_key}
        params = {
            "address": token_address,
            "type": "1", # 1 for token, 2 for pool
            "time_from": str(start_time),
            "time_to": str(end_time),
            "resolution": resolution
        }
        
        session = await self._get_session()
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", {}).get("items", [])
            else:
                error_text = await response.text()
                raise Exception(f"Failed to fetch historical data: {error_text}")
                    
    async def get_price(self, token_address: str) -> float:
        """
        Get current price of a token.
        If no API key is available, returns mock data for testing.
        
        Args:
            token_address: The Solana token address
            
        Returns:
            Current price in USD
        """
        url = f"{self.base_url}/public/price"
        headers = {"X-API-KEY": self.api_key}
        params = {"address": token_address}
        
        session = await self._get_session()
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return float(data.get("data", {}).get("value", 0))
            else:
                error_text = await response.text()
                raise Exception(f"Failed to fetch price: {error_text}")
                    
    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """
        Get token information.
        If no API key is available, returns mock data for testing.
        
        Args:
            token_address: The Solana token address
            
        Returns:
            Token information including name, symbol, decimals, etc.
        """
        url = f"{self.base_url}/public/token_list"
        headers = {"X-API-KEY": self.api_key}
        params = {"address": token_address}
        
        session = await self._get_session()
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", {}).get("tokens", [{}])[0]
            else:
                error_text = await response.text()
                raise Exception(f"Failed to fetch token info: {error_text}") 