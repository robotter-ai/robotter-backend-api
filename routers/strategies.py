from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi import FastAPI
from contextlib import asynccontextmanager

from services.libert_ai_service import LibertAIService
from routers.strategies_models import (
    ParameterSuggestionRequest,
    ParameterSuggestionResponse,
    StrategyConfig,
    StrategyRegistry,
    StrategyNotFoundError,
    StrategyValidationError,
    StrategyError,
    StrategyType
)

# Create a libert_ai_service instance
libert_ai_service = LibertAIService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize contexts on startup
    try:
        # Load strategies using auto-discovery
        print("Initializing LibertAI contexts...")
        strategies = StrategyRegistry.get_all_strategies()
        await libert_ai_service.initialize_contexts(strategies)
        print(f"Successfully initialized contexts for {len(strategies)} strategies")
    except Exception as e:
        print(f"Error initializing LibertAI contexts: {str(e)}")
        # Re-raise the exception to prevent app startup if context initialization fails
        raise
    yield
    # Cleanup on shutdown if needed
    print("Cleaning up LibertAI contexts...")

# Create the FastAPI app with the lifespan handler
app = FastAPI(lifespan=lifespan)
router = APIRouter()

responses = {
    400: {
        "description": "Bad Request - Invalid parameters or configuration",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Parameter Validation Error",
                        "value": {"detail": "Parameter 'stop_loss' value 0.5 is above maximum 0.1"}
                    },
                    "strategy_error": {
                        "summary": "Strategy Configuration Error",
                        "value": {"detail": "Unknown parameter: invalid_param"}
                    }
                }
            }
        }
    },
    404: {
        "description": "Not Found - Strategy does not exist",
        "content": {
            "application/json": {
                "example": {"detail": "Strategy 'unknown_strategy' not found"}
            }
        }
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {"detail": "Error processing backtesting results: Invalid data format"}
                    },
                    "unexpected_error": {
                        "summary": "Unexpected Error",
                        "value": {"detail": "An unexpected error occurred"}
                    }
                }
            }
        }
    }
}

@router.get(
    "/strategies",
    response_model=Dict[str, StrategyConfig],
    responses={
        200: {
            "description": "Successfully retrieved all available strategies",
            "content": {
                "application/json": {
                    "example": {
                        "bollinger_v1": {
                            "mapping": {
                                "id": "bollinger_v1",
                                "config_class": "BollingerConfig",
                                "module_path": "bots.controllers.directional_trading.bollinger_v1",
                                "strategy_type": "directional_trading",
                                "display_name": "Bollinger Bands Strategy",
                                "description": "Buys when price is low and sells when price is high based on Bollinger Bands."
                            },
                            "parameters": {
                                "stop_loss": {
                                    "name": "stop_loss",
                                    "type": "Decimal",
                                    "required": True,
                                    "default": "0.03",
                                    "display_name": "Stop Loss",
                                    "description": "Stop loss percentage",
                                    "group": "Risk Management",
                                    "is_advanced": False,
                                    "constraints": {
                                        "min_value": 0,
                                        "max_value": 0.1
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        **responses
    },
    summary="Get All Strategies",
    description="""
    Retrieve all available trading strategies and their configurations.
    
    Returns a dictionary where:
    - Keys are strategy IDs (e.g., "bollinger_v1", "supertrend_v1")
    - Values are complete strategy configurations including:
        - Mapping information (ID, type, display name, etc.)
        - Parameters with their constraints and metadata
        
    The strategies are grouped into three types:
    - Directional Trading: Strategies that follow market trends
    - Market Making: Strategies that provide market liquidity
    - Generic: Other types of strategies (e.g., arbitrage)
    
    Optional query parameter:
    - strategy_type: Filter strategies by type (directional_trading, market_making, generic)
    """
)
async def get_strategies(strategy_type: Optional[StrategyType] = None) -> Dict[str, StrategyConfig]:
    """Get all available strategies and their configurations."""
    try:
        if strategy_type:
            strategies = StrategyRegistry.get_strategies_by_type(strategy_type)
            return {s.id: s for s in strategies}
        return StrategyRegistry.get_all_strategies()
    except StrategyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error while fetching strategies: {str(e)}"
        )

@router.get(
    "/strategies/{strategy_id}",
    response_model=StrategyConfig,
    responses={
        200: {
            "description": "Successfully retrieved strategy details",
            "content": {
                "application/json": {
                    "example": {
                        "mapping": {
                            "id": "bollinger_v1",
                            "config_class": "BollingerConfig",
                            "module_path": "bots.controllers.directional_trading.bollinger_v1",
                            "strategy_type": "directional_trading",
                            "display_name": "Bollinger Bands Strategy",
                            "description": "Buys when price is low and sells when price is high based on Bollinger Bands."
                        },
                        "parameters": {
                            "stop_loss": {
                                "name": "stop_loss",
                                "type": "Decimal",
                                "required": True,
                                "default": "0.03",
                                "display_name": "Stop Loss",
                                "description": "Stop loss percentage",
                                "group": "Risk Management",
                                "is_advanced": False,
                                "constraints": {
                                    "min_value": 0,
                                    "max_value": 0.1
                                }
                            }
                        }
                    }
                }
            }
        },
        **responses
    },
    summary="Get Strategy Details",
    description="""
    Returns detailed information about a specific strategy, including all its parameters and configuration options.
    
    Use this endpoint to:
    1. Get the complete list of parameters needed for the strategy
    2. Understand parameter constraints (min/max values, valid options)
    3. See default values and parameter descriptions
    4. Determine which parameters are required vs optional
    
    This information is essential for:
    - Configuring a strategy for backtesting
    - Understanding parameter relationships
    - Setting up proper risk management
    - Optimizing strategy performance
    """
)
async def get_strategy_details(strategy_id: str) -> StrategyConfig:
    """Get detailed information about a specific strategy"""
    try:
        return StrategyRegistry.get_strategy(strategy_id)
    except StrategyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching strategy details: {str(e)}"
        )

@router.post(
    "/strategies/suggest-parameters",
    response_model=ParameterSuggestionResponse,
    responses={
        200: {
            "description": "Successfully generated parameter suggestions",
            "content": {
                "application/json": {
                    "example": {
                        "suggestions": [
                            {
                                "parameter_name": "stop_loss",
                                "suggested_value": "0.02",
                                "reasoning": "Based on current market volatility, a 2% stop loss provides good protection while allowing reasonable profit potential.",
                                "differs_from_default": True,
                                "differs_from_provided": True
                            }
                        ],
                        "summary": "Suggestions optimized for current market conditions with focus on risk management."
                    }
                }
            }
        },
        **responses
    },
    summary="Get Parameter Suggestions",
    description="""
    Get AI-powered suggestions for strategy parameters based on current market conditions.
    
    This endpoint uses LibertAI to analyze:
    - Current market conditions
    - Historical performance
    - Risk parameters
    - Strategy characteristics
    
    And provides:
    - Suggested parameter values
    - Reasoning for each suggestion
    - Comparison with defaults
    - Overall strategy summary
    
    You can:
    - Provide partial parameters and get suggestions for the rest
    - Request suggestions for specific parameters only
    - Get suggestions for all parameters
    
    The suggestions aim to optimize for:
    - Risk management
    - Market conditions
    - Strategy effectiveness
    - Historical performance patterns
    """
)
async def suggest_parameters(request: ParameterSuggestionRequest) -> ParameterSuggestionResponse:
    try:
        # Get strategy using the registry
        try:
            strategy = StrategyRegistry.get_strategy(request.strategy_id)
        except StrategyNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        
        # Validate parameters against constraints
        try:
            validate_parameters(strategy, request.parameters)
        except StrategyValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        # Ensure context is initialized for this strategy
        if request.strategy_id not in libert_ai_service.strategy_slot_map:
            print(f"Re-initializing context for strategy {request.strategy_id}")
            await libert_ai_service.initialize_contexts({request.strategy_id: strategy})
        
        try:
            # Get suggestions from LibertAI
            suggestions = await libert_ai_service.get_parameter_suggestions(
                strategy_id=request.strategy_id,
                strategy_config=strategy.parameters,
                provided_params=request.parameters,
                requested_params=request.requested_parameters
            )
            
            # Extract summary from the last suggestion if it exists
            summary = "No suggestions available."
            if suggestions:
                # Remove the summary suggestion if it exists
                if suggestions[-1].parameter_name.lower() == "summary":
                    summary = suggestions[-1].reasoning
                    suggestions = suggestions[:-1]
            
            return ParameterSuggestionResponse(
                suggestions=suggestions,
                summary=summary
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting parameter suggestions: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error processing parameter suggestions: {str(e)}"
        )

def validate_parameters(strategy: StrategyConfig, parameters: Dict[str, Any]) -> None:
    """Validate parameters against their constraints"""
    for param_name, value in parameters.items():
        if param_name not in strategy.parameters:
            raise StrategyValidationError(f"Unknown parameter: {param_name}")
            
        param = strategy.parameters[param_name]
        constraints = param.constraints
        
        if constraints:
            if constraints.min_value is not None and value < constraints.min_value:
                raise StrategyValidationError(
                    f"Parameter {param_name} value {value} is below minimum {constraints.min_value}"
                )
                
            if constraints.max_value is not None and value > constraints.max_value:
                raise StrategyValidationError(
                    f"Parameter {param_name} value {value} is above maximum {constraints.max_value}"
                )
                
            if constraints.valid_values is not None and value not in constraints.valid_values:
                raise StrategyValidationError(
                    f"Parameter {param_name} value {value} is not one of the valid values: {constraints.valid_values}"
                )
