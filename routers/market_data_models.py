from enum import Enum
import time
from pydantic import BaseModel
from typing import List

class CandleInterval(Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"

class CandleConnector(Enum):
    BIRDEYE = "birdeye"
    BINANCE = "binance"

class HistoricalCandlesConfig(BaseModel):
    connector_name: CandleConnector = CandleConnector.BIRDEYE
    market_address: str = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"  # Mango SOL-PERP
    interval: CandleInterval = CandleInterval.FIFTEEN_MINUTES
    start_time: int = int(time.time()) - 60 * 60 * 24 * 7 # 1 week
    end_time: int = int(time.time())

class CandleData(BaseModel):
    o: float
    h: float
    l: float
    c: float
    v: float
    unixTime: int
    address: str
    type: str

class HistoricalCandlesResponse(BaseModel):
    data: List[CandleData]