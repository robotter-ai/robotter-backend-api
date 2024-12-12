import pytest
from services.libert_ai_service import LibertAIService
from routers.strategies_models import (
    ParameterSuggestion,
    discover_strategies,
)
from typing import Any
from dataclasses import dataclass

@pytest.fixture
def libert_ai_service():
    service = LibertAIService()
    return service

@pytest.fixture
def strategy_configs():
    """Load all available strategies"""
    return discover_strategies()

@pytest.fixture
def bollinger_strategy(strategy_configs):
    """Get the Bollinger strategy configuration"""
    return strategy_configs["bollinger_v1"]

@pytest.mark.asyncio
async def test_initialize_system_context(libert_ai_service):
    """Test system context initialization"""
    await libert_ai_service._initialize_system_context()

@pytest.mark.asyncio
async def test_initialize_strategy_context(libert_ai_service, bollinger_strategy):
    """Test strategy context initialization"""
    with open(f"bots/{bollinger_strategy.mapping.module_path.split('bots.')[-1].replace('.', '/')}.py", "r") as f:
        strategy_code = f.read()
    
    await libert_ai_service._initialize_strategy_context(
        strategy_mapping=bollinger_strategy.mapping,
        strategy_config=bollinger_strategy.parameters,
        strategy_code=strategy_code,
        slot_id=0
    )

@pytest.mark.asyncio
async def test_get_parameter_suggestions(libert_ai_service, bollinger_strategy):
    """Test parameter suggestion generation"""
    
    libert_ai_service.strategy_slot_map["bollinger_v1"] = 0

    suggestions = await libert_ai_service.get_parameter_suggestions(
        strategy_id="bollinger_v1",
        strategy_config=bollinger_strategy.parameters,
        provided_params={"bb_std": 2.0}
    )
    
    # Verify suggestions are part of the bollinger_strategy.parameters
    for suggestion in suggestions:
        assert suggestion.parameter_name in bollinger_strategy.parameters or suggestion.parameter_name == "summary"

@pytest.mark.asyncio
async def test_parse_ai_response(libert_ai_service):
    """Test AI response parsing"""
    ai_response = {
        "choices": [{
            "message": {
                "content": """
PARAMETER: bb_length
VALUE: 100
REASONING: Standard length for Bollinger Bands calculation provides reliable signals while filtering out noise.

PARAMETER: bb_long_threshold
VALUE: 0.2
REASONING: Enter long positions when price is 20% below the middle band, indicating oversold conditions.

SUMMARY: These parameters are optimized for mean reversion trading using Bollinger Bands.
"""
            }
        }]
    }
    
    # Mock strategy config with proper parameter objects
    @dataclass
    class MockParameter:
        name: str
        default: Any
        required: bool = True
        type: str = "float"
        
    strategy_config = {
        "bb_length": MockParameter(
            name="BB Length",
            default=20,
            type="int"
        ),
        "bb_long_threshold": MockParameter(
            name="BB Long Threshold",
            default=0.1,
            type="float"
        )
    }
    
    provided_params = {
        "bb_length": 20
    }
    
    suggestions = libert_ai_service._parse_ai_response(
        ai_response,
        strategy_config=strategy_config,
        provided_params=provided_params
    )
    
    assert len(suggestions) == 3  # 2 parameters + summary
    assert all(isinstance(s, ParameterSuggestion) for s in suggestions)
    assert suggestions[0].parameter_name == "bb_length"
    assert suggestions[0].suggested_value == "100"
    assert suggestions[0].differs_from_default is True  # 100 vs default 20
    assert suggestions[0].differs_from_provided is True  # 100 vs provided 20
    assert suggestions[1].parameter_name == "bb_long_threshold"
    assert suggestions[1].suggested_value == "0.2"
    assert suggestions[1].differs_from_default is True  # 0.2 vs default 0.1
    assert suggestions[1].differs_from_provided is False  # Not provided
    assert suggestions[2].parameter_name == "summary"
    assert suggestions[2].suggested_value == "These parameters are optimized for mean reversion trading using Bollinger Bands."

@pytest.mark.asyncio
async def test_parse_ai_response_handles_invalid_format(libert_ai_service):
    """Test handling of invalid AI response format"""
    invalid_response = {
        "choices": [{
            "message": {
                "content": "Invalid format response"
            }
        }]
    }
    
    # Mock empty config with proper parameter objects
    strategy_config = {}
    provided_params = {}
    
    suggestions = libert_ai_service._parse_ai_response(
        invalid_response,
        strategy_config=strategy_config,
        provided_params=provided_params
    )
    assert suggestions == []

@pytest.mark.asyncio
async def test_get_specific_parameter_suggestions(libert_ai_service, bollinger_strategy):
    """Test getting suggestions for specific parameters"""
    
    libert_ai_service.strategy_slot_map["bollinger_v1"] = 0

    # Request suggestions for specific parameters
    requested_params = ["bb_length", "bb_long_threshold"]
    suggestions = await libert_ai_service.get_parameter_suggestions(
        strategy_id="bollinger_v1",
        strategy_config=bollinger_strategy.parameters,
        provided_params={"bb_std": 2.0},
        requested_params=requested_params
    )
    
    # Verify we only got suggestions for the requested parameters (plus summary)
    assert len(suggestions) == 3  # 2 requested parameters + summary
    suggestion_params = {s.parameter_name for s in suggestions if s.parameter_name != "summary"}
    assert suggestion_params == set(requested_params) 