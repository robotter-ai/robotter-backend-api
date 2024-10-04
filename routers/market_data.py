from fastapi import APIRouter
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
import aiohttp
import os
from dotenv import load_dotenv

from .market_data_models import CandleConnector, HistoricalCandlesConfig, HistoricalCandlesResponse, CandleData

router = APIRouter(tags=["Market Data"])
candles_factory = CandlesFactory()

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
    try:
        if config.connector_name == CandleConnector.BIRDEYE:
            return await fetch_birdeye_data(config)

        candles_config = CandlesConfig(
            connector=config.connector_name,
            trading_pair=config.trading_pair,
            interval=config.interval
        )
        candles = candles_factory.get_candle(candles_config)
        historical_data = await candles.get_historical_candles(config=config)
        
        # Convert DataFrame to HistoricalCandlesResponse
        candle_data = [
            CandleData(
                o=row['open'],
                h=row['high'],
                l=row['low'],
                c=row['close'],
                v=row['volume'],
                unixTime=int(row['timestamp']),
                address=config.market_address,
                type=config.interval.value
            )
            for _, row in historical_data.iterrows()
        ]
        return HistoricalCandlesResponse(data=candle_data)
    except Exception as e:
        return {"error": str(e)}
