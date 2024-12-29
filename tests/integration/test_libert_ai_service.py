import pytest
from services.libert_ai_service import LibertAIService
from routers.strategies_models import discover_strategies

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

@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_system_context(libert_ai_service):
    """Integration test: Test system context initialization"""
    await libert_ai_service._initialize_system_context()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_strategy_context(libert_ai_service, bollinger_strategy):
    """Integration test: Test strategy context initialization"""
    with open(f"bots/controllers/{bollinger_strategy.module_path.split('.')[-1]}.py", "r") as f:
        strategy_code = f.read()
    
    await libert_ai_service._initialize_strategy_context(
        strategy=bollinger_strategy,
        strategy_code=strategy_code,
        slot_id=0
    )

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_parameter_suggestions(libert_ai_service, bollinger_strategy):
    """Integration test: Test parameter suggestion generation"""
    
    libert_ai_service.strategy_slot_map["bollinger_v1"] = 0

    suggestions = await libert_ai_service.get_parameter_suggestions(
        strategy_id="bollinger_v1",
        strategy_config=bollinger_strategy.parameters,
        provided_params={"bb_std": 2.0}
    )
    
    # Verify suggestions are part of the bollinger_strategy.parameters
    for suggestion in suggestions:
        assert suggestion.parameter_name in bollinger_strategy.parameters or suggestion.parameter_name == "summary"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_specific_parameter_suggestions(libert_ai_service, bollinger_strategy):
    """Integration test: Test getting suggestions for specific parameters"""
    
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