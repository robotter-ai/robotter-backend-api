from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

class Trade(BaseModel):
    timestamp: int
    trading_pair: str
    side: str
    price: Decimal
    amount: Decimal
    type: str
    realized_pnl: Optional[Decimal]
    fee_amount: Decimal
    fee_token: str

class BotPerformanceStats(BaseModel):
    total_pnl: Decimal
    total_trades: int
    win_rate: float
    profit_loss_ratio: float
    sharpe_ratio: float = 0
    max_drawdown: float
    start_timestamp: int
    end_timestamp: int
    active_positions: List[dict]
    performance_by_trading_pair: dict

class TradeHistoryResponse(BaseModel):
    bot_name: str
    trades: List[Trade]

class PerformanceResponse(BaseModel):
    bot_name: str
    stats: BotPerformanceStats 