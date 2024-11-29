from typing import Dict, List, Optional, Union
from decimal import Decimal
from pydantic import BaseModel, Field


class TradeLog(BaseModel):
    """A single trade executed by the bot"""
    timestamp: int = Field(..., description="Unix timestamp of the trade")
    trading_pair: str = Field(..., description="Trading pair symbol (e.g. 'BTC-USDT')")
    side: str = Field(..., description="Trade side ('buy' or 'sell')")
    price: Decimal = Field(..., description="Price at which the trade was executed")
    amount: Decimal = Field(..., description="Amount of base asset traded")
    type: str = Field(..., description="Order type (e.g. 'market', 'limit')")
    realized_pnl: Optional[Decimal] = Field(None, description="Realized profit/loss from this trade")
    fee_amount: Decimal = Field(..., description="Fee amount charged for the trade")
    fee_token: str = Field(..., description="Token in which the fee was paid")


class Position(BaseModel):
    """Current active position information"""
    trading_pair: str = Field(..., description="Trading pair of the position")
    side: str = Field(..., description="Position side ('long' or 'short')")
    entry_price: Decimal = Field(..., description="Average entry price of the position")
    amount: Decimal = Field(..., description="Position size in base asset")
    leverage: Optional[float] = Field(None, description="Leverage used for the position")
    unrealized_pnl: Decimal = Field(..., description="Current unrealized profit/loss")
    liquidation_price: Optional[Decimal] = Field(None, description="Price at which position will be liquidated")


class ControllerPerformance(BaseModel):
    """Performance metrics for a single controller"""
    total_pnl: Decimal = Field(..., description="Total profit/loss (realized + unrealized)")
    total_trades: int = Field(..., description="Total number of trades executed")
    win_rate: float = Field(..., description="Percentage of profitable trades")
    profit_loss_ratio: float = Field(..., description="Ratio of average profit to average loss")
    sharpe_ratio: float = Field(0, description="Risk-adjusted return metric")
    max_drawdown: float = Field(..., description="Maximum peak to trough decline")
    start_timestamp: int = Field(..., description="Start time of performance tracking")
    end_timestamp: int = Field(..., description="Latest update time of performance metrics")
    active_positions: List[Position] = Field(default_factory=list, description="Currently open positions")
    close_type_counts: Dict[str, int] = Field(default_factory=dict, description="Count of different trade exit types")


class ControllerStatus(BaseModel):
    """Status and performance of a controller"""
    status: str = Field(..., description="Controller status ('running', 'stopped', or 'error')")
    performance: Optional[ControllerPerformance] = Field(None, description="Performance metrics if status is 'running'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")


class BotStatus(BaseModel):
    """Overall bot status including all controllers"""
    status: str = Field(..., description="Overall bot status ('running', 'stopped', or 'error')")
    performance: Dict[str, ControllerStatus] = Field(..., description="Performance by controller")
    error_logs: List[dict] = Field(default_factory=list, description="Recent error logs")
    general_logs: List[dict] = Field(default_factory=list, description="Recent general logs")


class LogEntry(BaseModel):
    """A log entry from the bot"""
    timestamp: int = Field(..., description="Unix timestamp of the log entry")
    level_name: str = Field(..., description="Log level (INFO, ERROR, etc.)")
    message: str = Field(..., description="Log message content")
    extra: Optional[Dict] = Field(None, description="Additional log metadata") 