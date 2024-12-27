from fastapi import APIRouter, HTTPException, status
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from hummingbot.strategy_v2.backtesting.controllers_backtesting.directional_trading_backtesting import (
    DirectionalTradingBacktesting,
)
from hummingbot.strategy_v2.backtesting.controllers_backtesting.market_making_backtesting import MarketMakingBacktesting

from config import CONTROLLERS_MODULE, CONTROLLERS_PATH
from routers.backtest_models import BacktestResponse, BacktestResults, BacktestingConfig, ExecutorInfo, ProcessedData
from routers.strategies_models import StrategyError

router = APIRouter(tags=["Market Backtesting"])
candles_factory = CandlesFactory()
directional_trading_backtesting = DirectionalTradingBacktesting()
market_making_backtesting = MarketMakingBacktesting()

BACKTESTING_ENGINES = {
    "directional_trading": directional_trading_backtesting,
    "market_making": market_making_backtesting
}

class BacktestError(StrategyError):
    """Base class for backtesting-related errors"""

class BacktestConfigError(BacktestError):
    """Raised when there's an error in the backtesting configuration"""

class BacktestEngineError(BacktestError):
    """Raised when there's an error during backtesting execution"""

responses = {
    400: {
        "description": "Bad Request - Invalid backtesting configuration",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_config": {
                        "summary": "Invalid Configuration",
                        "value": {"detail": "Invalid controller configuration: Missing required parameter 'stop_loss'"}
                    },
                    "invalid_time": {
                        "summary": "Invalid Time Range",
                        "value": {"detail": "Invalid time range: end_time (1000) must be greater than start_time (2000)"}
                    },
                    "invalid_engine": {
                        "summary": "Invalid Engine Type",
                        "value": {"detail": "Backtesting engine for controller type 'unknown' not found. Available types: ['directional_trading', 'market_making']"}
                    }
                }
            }
        }
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "execution_error": {
                        "summary": "Execution Error",
                        "value": {"detail": "Error during backtesting execution: Failed to fetch market data"}
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {"detail": "Error processing backtesting results: Invalid data format"}
                    }
                }
            }
        }
    }
}

@router.post(
    "/backtest",
    response_model=BacktestResponse,
    responses={
        200: {
            "description": "Successfully ran backtesting simulation",
            "content": {
                "application/json": {
                    "example": {
                        "executors": [{
                            "id": "executor_1",
                            "trades": 42,
                            "win_rate": 0.65,
                            "profit_loss": 1250.50
                        }],
                        "processed_data": {
                            "features": {
                                "price": [100.0, 101.0, 99.5],
                                "volume": [1000, 1200, 800],
                                "indicators": {
                                    "ma_20": [99.5, 100.2, 100.8]
                                }
                            }
                        },
                        "results": {
                            "total_trades": 42,
                            "win_rate": 0.65,
                            "profit_loss": 1250.50,
                            "sharpe_ratio": 1.8,
                            "max_drawdown": 0.15,
                            "roi": 0.25
                        }
                    }
                }
            }
        },
        **responses
    },
    summary="Run Strategy Backtesting",
    description="""
    Run a backtesting simulation for a trading strategy with historical market data.
    
    The backtesting process:
    1. Loads the strategy configuration
    2. Fetches historical market data for the specified time range
    3. Simulates trading with the strategy
    4. Analyzes performance and generates statistics
    
    Supports two types of backtesting engines:
    - Directional Trading: For trend-following and momentum strategies
    - Market Making: For liquidity provision strategies
    
    Returns comprehensive results including:
    - Executor statistics (trades, win rate, P&L)
    - Processed market data and indicators
    - Overall performance metrics:
        - Total trades executed
        - Win rate
        - Profit/Loss
        - Sharpe ratio
        - Maximum drawdown
        - Return on Investment (ROI)
    
    Time range requirements:
    - start_time must be before end_time
    - Minimum time range: 1 hour
    - Maximum time range: 90 days
    """
)
async def run_backtesting(backtesting_config: BacktestingConfig) -> BacktestResponse:
    try:
        # Load and validate controller config
        try:
            if isinstance(backtesting_config.config, str):
                controller_config = BacktestingEngineBase.get_controller_config_instance_from_yml(
                    config_path=backtesting_config.config,
                    controllers_conf_dir_path=CONTROLLERS_PATH,
                    controllers_module=CONTROLLERS_MODULE
                )
            else:
                controller_config = BacktestingEngineBase.get_controller_config_instance_from_dict(
                    config_data=backtesting_config.config,
                    controllers_module=CONTROLLERS_MODULE
                )
        except Exception as e:
            raise BacktestConfigError(f"Invalid controller configuration: {str(e)}")

        # Get and validate backtesting engine
        backtesting_engine = BACKTESTING_ENGINES.get(controller_config.controller_type)
        if not backtesting_engine:
            raise BacktestConfigError(
                f"Backtesting engine for controller type {controller_config.controller_type} not found. "
                f"Available types: {list(BACKTESTING_ENGINES.keys())}"
            )

        # Validate time range
        if backtesting_config.end_time <= backtesting_config.start_time:
            raise BacktestConfigError(
                f"Invalid time range: end_time ({backtesting_config.end_time}) must be greater than "
                f"start_time ({backtesting_config.start_time})"
            )

        try:
            # Run backtesting
            backtesting_results = await backtesting_engine.run_backtesting(
                controller_config=controller_config,
                trade_cost=backtesting_config.trade_cost,
                start=int(backtesting_config.start_time),
                end=int(backtesting_config.end_time),
                backtesting_resolution=backtesting_config.backtesting_resolution
            )
        except Exception as e:
            raise BacktestEngineError(f"Error during backtesting execution: {str(e)}")

        try:
            # Process results
            processed_data = backtesting_results["processed_data"]["features"].fillna(0).to_dict()
            executors_info = [ExecutorInfo(**e.to_dict()) for e in backtesting_results["executors"]]
            results = backtesting_results["results"]
            results["sharpe_ratio"] = results["sharpe_ratio"] if results["sharpe_ratio"] is not None else 0
            
            return BacktestResponse(
                executors=executors_info,
                processed_data=ProcessedData(features=processed_data),
                results=BacktestResults(**results)
            )
        except Exception as e:
            raise BacktestError(f"Error processing backtesting results: {str(e)}")

    except BacktestConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BacktestEngineError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except BacktestError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during backtesting: {str(e)}"
        )