from fastapi import APIRouter, HTTPException, status
from routers.backtest_models import BacktestResponse, BacktestingConfig
from services.backtesting_service import BacktestingService, BacktestConfigError, BacktestEngineError, BacktestError

router = APIRouter(tags=["Market Backtesting"])
backtesting_service = BacktestingService()

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
                    },
                    "invalid_strategy": {
                        "summary": "Invalid Strategy",
                        "value": {"detail": "Strategy 'unknown_strategy' not found. Use GET /strategies to see available strategies."}
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
    
    Required Configuration:
    - strategy_id: ID of the strategy to backtest (get available strategies from GET /strategies)
    - trading_pair: The trading pair to backtest on (e.g., "BTC-USDT")
    - Other parameters specific to the chosen strategy
    
    Time range requirements:
    - start_time must be before end_time
    - Minimum time range: 1 hour
    - Maximum time range: 90 days
    """
)
async def run_backtesting(backtesting_config: BacktestingConfig) -> BacktestResponse:
    try:
        return await backtesting_service.run_backtesting(backtesting_config)
    except BacktestConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BacktestEngineError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except BacktestError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during backtesting: {str(e)}"
        )

@router.get(
    "/backtest/engines",
    response_model=dict,
    summary="Get Available Backtesting Engines",
    description="Returns a list of available backtesting engines and their types."
)
def get_available_engines():
    return backtesting_service.get_available_engines()

@router.get(
    "/backtest/engines/{engine_type}/config",
    response_model=dict,
    summary="Get Engine Configuration Schema",
    description="Returns the configuration schema for a specific backtesting engine type."
)
def get_engine_config_schema(engine_type: str):
    schema = backtesting_service.get_engine_config_schema(engine_type)
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engine type '{engine_type}' not found"
        )
    return schema