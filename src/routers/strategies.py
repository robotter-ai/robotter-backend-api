from typing import Dict, Any
from fastapi import APIRouter, HTTPException
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
    StrategyError
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

@router.get("/strategies")
async def get_strategies() -> Dict[str, StrategyConfig]:
    """Get all available strategies and their configurations."""
    try:
        return StrategyRegistry.get_all_strategies()
    except StrategyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while fetching strategies: {str(e)}"
        )

@router.post("/strategies/suggest-parameters")
async def suggest_parameters(request: ParameterSuggestionRequest) -> ParameterSuggestionResponse:
    """
    Suggest parameter values for a strategy based on the provided parameters.
    Uses LibertAI to analyze and suggest optimal values for missing or requested parameters.
    
    If requested_parameters is provided, will only suggest values for those specific parameters.
    Otherwise, will suggest values for all missing required parameters.
    """
    try:
        # Get strategy using the registry
        try:
            strategy = StrategyRegistry.get_strategy(request.strategy_id)
        except StrategyNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # Validate parameters against constraints
        try:
            validate_parameters(strategy, request.parameters)
        except StrategyValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
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
                status_code=500,
                detail=f"Error getting parameter suggestions: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
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