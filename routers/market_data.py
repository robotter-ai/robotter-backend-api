from fastapi import APIRouter, HTTPException, Depends
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
import aiohttp
import os
from dotenv import load_dotenv
import numpy as np
from services.accounts_service import AccountsService

from .market_data_models import CandleConnector, HistoricalCandlesConfig, HistoricalCandlesResponse, CandleData

router = APIRouter(tags=["Market Data"])
candles_factory = CandlesFactory()

# Assuming you have a way to get the AccountsService instance
accounts_service = AccountsService()

async def fetch_birdeye_data(config: HistoricalCandlesConfig) -> HistoricalCandlesResponse:
    load_dotenv()
    birdeye_api_key = os.getenv("BIRDEYE_API_KEY")
    if not birdeye_api_key:
        raise ValueError("BIRDEYE_API_KEY not found in environment variables")

    url = f"https://public-api.birdeye.so/defi/ohlcv?address={config.market_address}&type={config.interval.value}&time_from={config.start_time}&time_to={config.end_time}"
    headers = {
        "accept": "application/json",
        "X-API-KEY": birdeye_api_key
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                candle_data = [CandleData(**item) for item in data['data']['items']]
                return HistoricalCandlesResponse(data=candle_data)
            else:
                raise Exception(f"Failed to fetch data: {response.status}")

@router.post("/historical-candles", response_model=HistoricalCandlesResponse)
async def get_historical_candles(config: HistoricalCandlesConfig) -> HistoricalCandlesResponse:
    if config.connector_name == CandleConnector.BIRDEYE:
        return await fetch_birdeye_data(config)

    candles_config = CandlesConfig(
        connector=config.connector_name,
        trading_pair=config.trading_pair,
        interval=config.interval
    )
    candles = candles_factory.get_candle(candles_config)
    historical_data = await candles.get_historical_candles(config=config)
    
    # Convert DataFrame to numpy array for faster processing
    data_array = historical_data[['open', 'high', 'low', 'close', 'volume', 'timestamp']].to_numpy()
    
    # Use numpy vectorization to create CandleData objects
    candle_data = [
        CandleData(
            o=float(o),
            h=float(h),
            l=float(l),
            c=float(c),
            v=float(v),
            unixTime=int(t),
            address=config.market_address,
            type=config.interval.value
        )
        for o, h, l, c, v, t in data_array
    ]
    
    return HistoricalCandlesResponse(data=candle_data)
    

@router.get("/markets")
async def get_markets(account_name: str = "master_account"):
    gateway_client = accounts_service.get_gateway_client(account_name)
    response = await gateway_client.get_clob_markets("mango_perpetual_solana_mainnet-beta", "solana", "mainnet")
    print(response)
    
    if response.get("success"):
        markets = response.get("markets", [])
        return {"markets": markets}
    else:
        raise HTTPException(status_code=500, detail="Failed to fetch Mango markets from gateway")