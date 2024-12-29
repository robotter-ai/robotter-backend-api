from typing import Dict, Any, Optional, List
from decimal import Decimal
from routers.strategies_models import StrategyRegistry, StrategyNotFoundError
from routers.backtest_models import BacktestingConfig, BacktestResponse
from hummingbot.strategy_v2.backtesting.controllers_backtesting.directional_trading_backtesting import DirectionalTradingBacktesting
from hummingbot.strategy_v2.backtesting.controllers_backtesting.market_making_backtesting import MarketMakingBacktesting

class BacktestError(Exception):
    """Base class for backtesting errors"""
    pass

class BacktestConfigError(BacktestError):
    """Error in backtesting configuration"""
    pass

class BacktestEngineError(BacktestError):
    """Error in backtesting engine execution"""
    pass

class BacktestingService:
    """Service for running backtesting operations"""
    
    def __init__(self):
        self.directional_trading_backtesting = DirectionalTradingBacktesting()
        self.market_making_backtesting = MarketMakingBacktesting()
        self.backtesting_engines = {
            "directional_trading": self.directional_trading_backtesting,
            "market_making": self.market_making_backtesting
        }
    
    def validate_time_range(self, start_time: int, end_time: int) -> None:
        """Validate the time range for backtesting"""
        if start_time >= end_time:
            raise BacktestConfigError("Invalid time range: start time must be before end time")
    
    def transform_strategy_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform API strategy config to controller config"""
        try:
            strategy_id = config.get("strategy_id")
            if not strategy_id:
                raise BacktestConfigError("Missing strategy_id in configuration")
            
            # Get strategy info from registry
            strategy = StrategyRegistry.get_strategy(strategy_id)
            
            # Keep all configuration parameters except strategy_id
            filtered_config = {
                k: v for k, v in config.items()
                if k != "strategy_id"
            }
            
            # Add required controller configuration
            controller_config = {
                "controller_type": strategy.strategy_type.value,
                "controller_name": strategy_id,
                **filtered_config
            }
            
            return controller_config
        except StrategyNotFoundError as e:
            raise BacktestConfigError(f"Strategy not found: {str(e)}")
        except Exception as e:
            raise BacktestConfigError(f"Error transforming strategy config: {str(e)}")
    
    def get_available_engines(self) -> Dict[str, str]:
        """Get available backtesting engines"""
        return {
            engine_type: engine.__class__.__name__
            for engine_type, engine in self.backtesting_engines.items()
        }
    
    def get_engine_config_schema(self, engine_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration schema for a specific backtesting engine type
        
        Args:
            engine_type: The type of backtesting engine
            
        Returns:
            A dictionary containing the configuration schema, or None if engine type not found
        """
        engine = self.backtesting_engines.get(engine_type)
        if not engine:
            return None
            
        # Get all strategies of this engine type
        strategies = StrategyRegistry.get_strategies_by_type(engine_type)
        
        if not strategies:
            return None
            
        # Build schema based on common parameters across all strategies of this type
        schema = {
            "type": "object",
            "properties": {
                "strategy_id": {
                    "type": "string",
                    "description": "ID of the strategy to backtest",
                    "enum": [s.id for s in strategies]
                },
                "trading_pair": {
                    "type": "string",
                    "description": "Trading pair to backtest (e.g., BTC-USDT)",
                    "pattern": "^[A-Z0-9]+-[A-Z0-9]+$"
                },
                "leverage": {
                    "type": "integer",
                    "description": "Leverage multiplier",
                    "default": 1,
                    "minimum": 1
                },
                "interval": {
                    "type": "string",
                    "description": "Trading interval",
                    "default": "1m",
                    "enum": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
                },
                "stop_loss": {
                    "type": "number",
                    "description": "Stop loss percentage (e.g., 0.03 for 3%)",
                    "default": 0.03,
                    "minimum": 0,
                    "maximum": 1
                },
                "take_profit": {
                    "type": "number",
                    "description": "Take profit percentage (e.g., 0.02 for 2%)",
                    "default": 0.02,
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["strategy_id", "trading_pair"],
            "additionalProperties": True
        }
        
        return schema

    async def run_backtesting(self, config: BacktestingConfig) -> BacktestResponse:
        """Run backtesting with the given configuration"""
        try:
            # Validate time range
            self.validate_time_range(config.start_time, config.end_time)
            
            # Transform strategy config
            transformed_config = self.transform_strategy_config(config.config)
            
            # Get the appropriate backtesting engine
            engine_type = transformed_config.get("controller_type")
            engine = self.backtesting_engines.get(engine_type)
            if not engine:
                raise BacktestConfigError(f"Backtesting engine '{engine_type}' not found")
            
            # Run backtesting
            try:
                results = await engine.run_backtesting(
                    controller_config=transformed_config,
                    start=config.start_time,
                    end=config.end_time,
                    backtesting_resolution=config.backtesting_resolution,
                    trade_cost=config.trade_cost
                )
                
                # Process results to match BacktestResponse structure
                if isinstance(results, dict):
                    processed_results = {
                        "executors": results.get("executors", []),
                        "results": results.get("results", {}),
                        "processed_data": results.get("processed_data", {})
                    }
                    return BacktestResponse(**processed_results)
                else:
                    raise BacktestEngineError("Invalid results format returned from backtesting engine")
            except BacktestEngineError as e:
                raise e
            except Exception as e:
                raise BacktestEngineError(f"Error during backtesting execution: {str(e)}")
        except BacktestError as e:
            raise e
        except Exception as e:
            raise BacktestError(f"Unexpected error during backtesting: {str(e)}") 