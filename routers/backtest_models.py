from typing import List, Dict, Any, Union
from pydantic import BaseModel, Field
from decimal import Decimal

class BacktestingConfig(BaseModel):
    start_time: int = 1672542000  # 2023-01-01 00:00:00
    end_time: int = 1672628400  # 2023-01-01 23:59:00
    backtesting_resolution: str = "1m"
    trade_cost: float = 0.0006
    config: Union[Dict, str]

class ExecutorInfo(BaseModel):
    id: str
    level_id: str
    timestamp: int
    connector_name: str
    trading_pair: str
    entry_price: Decimal
    amount: Decimal
    side: str
    leverage: int
    position_mode: str
    trades: int
    win_rate: float
    profit_loss: Decimal

class ProcessedData(BaseModel):
    features: Dict[str, List[Union[float, int, str]]]

class BacktestResults(BaseModel):
    total_pnl: Decimal
    total_trades: int
    win_rate: float
    profit_loss_ratio: float
    sharpe_ratio: float = Field(default=0)
    max_drawdown: float
    start_timestamp: int
    end_timestamp: int

class BacktestResponse(BaseModel):
    executors: List[ExecutorInfo]
    processed_data: ProcessedData
    results: BacktestResults