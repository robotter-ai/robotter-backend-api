from decimal import Decimal
from typing import Dict, Any, Optional

import pandas as pd
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from hummingbot.strategy_v2.backtesting.controllers_backtesting.directional_trading_backtesting import (
    DirectionalTradingBacktesting,
)
from hummingbot.strategy_v2.backtesting.controllers_backtesting.market_making_backtesting import MarketMakingBacktesting

from config import CONTROLLERS_MODULE
from routers.backtest_models import BacktestResponse, BacktestResults, BacktestingConfig, ExecutorInfo, ProcessedData
from routers.strategies_models import StrategyRegistry, StrategyError, StrategyNotFoundError

class BacktestError(StrategyError):
    """Base class for backtesting-related errors"""

class BacktestConfigError(BacktestError):
    """Raised when there's an error in the backtesting configuration"""

class BacktestEngineError(BacktestError):
    """Raised when there's an error during backtesting execution"""

class BacktestingService:
    def __init__(self):
        self.candles_factory = CandlesFactory()
        self.directional_trading_backtesting = DirectionalTradingBacktesting()
        self.market_making_backtesting = MarketMakingBacktesting()
        self.backtesting_engines = {
            "directional_trading": self.directional_trading_backtesting,
            "market_making": self.market_making_backtesting
        }

    def transform_strategy_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform API strategy config to controller config"""
        try:
            strategy_id = config.get("strategy_id")
            if not strategy_id:
                raise BacktestConfigError("Missing strategy_id in configuration")
            
            # Get strategy info from registry
            strategy = StrategyRegistry.get_strategy(strategy_id)
            
            # Get valid parameters for this strategy
            valid_params = set(strategy.parameters.keys())
            
            # Filter config to only include valid parameters
            filtered_config = {
                k: v for k, v in config.items() 
                if k != "strategy_id" and k in valid_params
            }
            
            # Add required controller configuration
            controller_config = {
                "controller_type": strategy.mapping.strategy_type.value,
                "controller_name": strategy.mapping.id,
                **filtered_config
            }
            
            return controller_config
        except StrategyNotFoundError as e:
            raise BacktestConfigError(f"Strategy not found: {str(e)}")
        except Exception as e:
            raise BacktestConfigError(f"Error transforming strategy config: {str(e)}")

    def validate_time_range(self, start_time: int, end_time: int):
        """Validate the backtesting time range"""
        if end_time <= start_time:
            raise BacktestConfigError(
                f"Invalid time range: end_time ({end_time}) must be greater than "
                f"start_time ({start_time})"
            )

    async def run_backtesting(self, config: BacktestingConfig) -> BacktestResponse:
        """Run a backtesting simulation"""
        try:
            # Transform and validate strategy config
            try:
                transformed_config = self.transform_strategy_config(config.config)
                controller_config = BacktestingEngineBase.get_controller_config_instance_from_dict(
                    config_data=transformed_config,
                    controllers_module=CONTROLLERS_MODULE
                )
            except BacktestConfigError as e:
                raise e
            except Exception as e:
                raise BacktestConfigError(f"Invalid controller configuration: {str(e)}")

            # Get and validate backtesting engine
            backtesting_engine = self.backtesting_engines.get(controller_config.controller_type)
            if not backtesting_engine:
                raise BacktestConfigError(
                    f"Backtesting engine for controller type {controller_config.controller_type} not found. "
                    f"Available types: {list(self.backtesting_engines.keys())}"
                )

            # Validate time range
            self.validate_time_range(config.start_time, config.end_time)

            try:
                # Run backtesting
                backtesting_results = await backtesting_engine.run_backtesting(
                    controller_config=controller_config,
                    trade_cost=config.trade_cost,
                    start=int(config.start_time),
                    end=int(config.end_time),
                    backtesting_resolution=config.backtesting_resolution
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
            raise e
        except BacktestEngineError as e:
            raise e
        except Exception as e:
            raise BacktestError(f"Unexpected error during backtesting: {str(e)}")

    def get_available_engines(self) -> Dict[str, str]:
        """Get a list of available backtesting engines"""
        return {
            engine_type: engine.__class__.__name__ 
            for engine_type, engine in self.backtesting_engines.items()
        }

    def get_engine_config_schema(self, engine_type: str) -> Optional[Dict[str, Any]]:
        """Get the configuration schema for a specific engine type"""
        engine = self.backtesting_engines.get(engine_type)
        if not engine:
            return None
        return engine.get_config_schema() 