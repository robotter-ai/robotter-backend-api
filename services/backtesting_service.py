from typing import Dict, Any, Optional, List
from decimal import Decimal
from routers.strategies_models import StrategyRegistry, StrategyNotFoundError
from routers.backtest_models import BacktestingConfig, BacktestResponse
from hummingbot.strategy_v2.backtesting. import DirectionalTradingBacktesting
from hummingbot.strategy_v2.backtesting.controllers_backtesting.market_making_backtesting import MarketMakingBacktesting

class BacktestError(Exception):
    """Base class for backtesting errors"""
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
            raise BacktestError("Invalid time range: start time must be before end time")
    
    def transform_strategy_config(self, config: Dict[str, Any]) -> Any:
        """Transform API strategy config to controller config"""
        controller_name = config.get("controller_name")
        if not controller_name:
            raise BacktestError("Missing controller_name in configuration")
        
        # Get strategy info from registry
        strategy = StrategyRegistry.get_strategy(controller_name)
        
        # Keep all configuration parameters except controller_name
        filtered_config = {k: v for k, v in config.items() if k != "controller_name"}
        
        # Add required controller configuration
        controller_config = {
            "controller_name": controller_name,
            "controller_type": strategy.strategy_type.value,
            "id": None,  # Required by base class
            "connector_name": filtered_config.get("connector_name"),
            "trading_pair": filtered_config.get("trading_pair"),
            "leverage": filtered_config.get("leverage", 1),
            "position_mode": filtered_config.get("position_mode", "ONEWAY"),
            "stop_loss": filtered_config.get("stop_loss"),
            "take_profit": filtered_config.get("take_profit"),
            "time_limit": filtered_config.get("time_limit", 60 * 60 * 24 * 7),  # 1 week default
            "trailing_stop": filtered_config.get("trailing_stop"),
            **filtered_config
        }
        
        # Import and configure the strategy
        module_path = f"bots.controllers.{strategy.strategy_type.value}.{controller_name}"
        try:
            module = __import__(module_path, fromlist=["*"])
            config_class = next(
                (getattr(module, name) for name in dir(module) 
                 if name.endswith(("ControllerConfig", "Config"))),
                None
            )
            if not config_class:
                raise BacktestError(f"Could not find config class in module {module_path}")
            
            # Add candles config if needed
            if "candles_connector" in filtered_config and "candles_trading_pair" in filtered_config:
                from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
                controller_config["candles_config"] = [CandlesConfig(
                    connector=filtered_config["candles_connector"],
                    trading_pair=filtered_config["candles_trading_pair"],
                    interval=filtered_config.get("interval", "1m"),
                    max_records=500
                )]
            
            return config_class(**controller_config)
            
        except ImportError:
            raise BacktestError(f"Could not import strategy module: {module_path}")
        except Exception as e:
            raise BacktestError(f"Error creating strategy config: {str(e)}")
    
    def get_available_engines(self) -> Dict[str, str]:
        """Get available backtesting engines"""
        return {
            engine_type: engine.__class__.__name__
            for engine_type, engine in self.backtesting_engines.items()
        }
    
    def get_engine_config_schema(self, engine_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration schema for a specific backtesting engine type"""
        engine = self.backtesting_engines.get(engine_type)
        if not engine:
            return None
            
        strategies = StrategyRegistry.get_strategies_by_type(engine_type)
        if not strategies:
            return None
            
        schema = {
            "type": "object",
            "properties": {
                "controller_name": {
                    "type": "string",
                    "description": "Name of the strategy controller to use",
                    "enum": [s.id for s in strategies]
                }
            },
            "required": ["controller_name"],
            "additionalProperties": True
        }
        
        try:
            # Import the base config classes
            from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase
            from hummingbot.strategy_v2.controllers.directional_trading_controller_base import DirectionalTradingControllerConfigBase
            from hummingbot.strategy_v2.controllers.market_making_controller_base import MarketMakingControllerConfigBase
            
            # Get the appropriate base class for this engine type
            base_config_class = {
                "directional_trading": DirectionalTradingControllerConfigBase,
                "market_making": MarketMakingControllerConfigBase,
                "generic": ControllerConfigBase
            }.get(engine_type)
            
            if not base_config_class:
                print(f"No base config class found for engine type: {engine_type}")
                return schema
                
            print(f"\nBase config class for {engine_type}: {base_config_class.__name__}")
            
            # Add fields from base classes first
            def add_fields_from_class(cls):
                print(f"\nProcessing class: {cls.__name__}")
                if not hasattr(cls, "__fields__"):
                    print(f"No __fields__ in {cls.__name__}")
                    return
                
                fields = cls.__fields__
                print(f"Fields in {cls.__name__}: {list(fields.keys())}")
                
                for field_name, field in fields.items():
                    if field_name in ["controller_type", "id"]:  # Allow controller_name through
                        continue
                        
                    field_info = field.field_info
                    field_schema = {
                        "type": self._get_json_schema_type(field.type_),
                        "description": field_info.description or field_name
                    }

                    if field.default is not None and not callable(field.default):
                        field_schema["default"] = field.default

                    if hasattr(field_info, "gt"):
                        field_schema["minimum"] = field_info.gt
                    if hasattr(field_info, "lt"):
                        field_schema["maximum"] = field_info.lt

                    schema["properties"][field_name] = field_schema
                    if field.required:
                        if field_name not in schema["required"]:
                            schema["required"].append(field_name)

            # Process all classes in the MRO chain except object
            for cls in reversed(base_config_class.__mro__[:-1]):
                add_fields_from_class(cls)
            
            # Get example strategy to determine additional fields
            example_strategy = strategies[0]
            module_path = f"bots.controllers.{engine_type}.{example_strategy.id}"
            
            print(f"\nTrying to import module: {module_path}")
            module = __import__(module_path, fromlist=["*"])
            
            # Find the strategy-specific config class
            strategy_specific_pattern = f"{example_strategy.id.title().replace('_', '')}Config"
            print(f"Looking for strategy-specific config class: {strategy_specific_pattern}")
            
            config_class = None
            for name in dir(module):
                if name.endswith(("ControllerConfig", "Config")):
                    cls = getattr(module, name)
                    print(f"Found potential config class: {name}")
                    # Skip CandlesConfig and classes not inheriting from ControllerConfigBase
                    if name == "CandlesConfig" or not issubclass(cls, ControllerConfigBase):
                        print(f"Skipping {name} - not a valid controller config")
                        continue
                    # Prefer strategy-specific config if found
                    if name == strategy_specific_pattern:
                        config_class = cls
                        break
                    # Otherwise take the first valid config class
                    if not config_class:
                        config_class = cls
            
            if config_class:
                print(f"\nFound strategy config class: {config_class.__name__}")
                # Process all classes in the strategy config's MRO chain except object
                for cls in reversed(config_class.__mro__[:-1]):
                    if cls not in base_config_class.__mro__:  # Skip classes we've already processed
                        add_fields_from_class(cls)
            
            print(f"\nFinal schema properties: {list(schema['properties'].keys())}")
            print(f"Final required fields: {schema['required']}")
            return schema
            
        except Exception as e:
            print(f"Error generating schema: {str(e)}")
            import traceback
            traceback.print_exc()
            return schema
    
    def _get_json_schema_type(self, python_type: type) -> str:
        """Convert Python type to JSON schema type"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            Decimal: "number"
        }
        return type_map.get(python_type, "string")

    async def run_backtesting(self, config: BacktestingConfig) -> BacktestResponse:
        """Run backtesting with the given configuration"""
        self.validate_time_range(config.start_time, config.end_time)
        
        strategy = StrategyRegistry.get_strategy(config.config["controller_name"])
        transformed_config = self.transform_strategy_config(config.config)
        
        engine_type = strategy.strategy_type.value
        engine = self.backtesting_engines.get(engine_type)
        if not engine:
            raise BacktestError(f"Backtesting engine '{engine_type}' not found")
        
        results = await engine.run_backtesting(
            controller_config=transformed_config,
            start=config.start_time,
            end=config.end_time,
            backtesting_resolution=config.backtesting_resolution,
            trade_cost=config.trade_cost
        )
        
        if not isinstance(results, dict):
            raise BacktestError("Invalid results format returned from backtesting engine")
            
        # Process results
        processed_data = results.get("processed_data", {})
        features = processed_data.get("features", {})
        
        if hasattr(features, "to_dict"):
            features = {col: features[col].tolist() for col in features.columns}
        
        # Prepare results with defaults
        results_data = results.get("results", {})
        default_results = {
            "total_pnl": Decimal("0"),
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "max_drawdown": 0.0,
            "start_timestamp": config.start_time,
            "end_timestamp": config.end_time
        }
        
        if results_data:
            for key, default in default_results.items():
                results_data.setdefault(key, default)
        else:
            results_data = default_results
        
        return BacktestResponse(
            executors=results.get("executors", []),
            results=results_data,
            processed_data={"features": features}
        ) 