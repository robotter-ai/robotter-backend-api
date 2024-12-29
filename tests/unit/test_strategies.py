import pytest
from unittest.mock import patch, MagicMock
from routers.strategies_models import (
    StrategyType,
    StrategyParameter,
    ParameterConstraints,
    ParameterGroup,
    DisplayType,
    discover_strategies,
    StrategyMapping
)

@pytest.fixture
def mock_strategy():
    """Create a mock strategy for testing"""
    return StrategyMapping(
        id="test_strategy",
        display_name="Test Strategy",
        description="Test description",
        strategy_type=StrategyType.DIRECTIONAL_TRADING,
        module_path="test.module",
        config_class="TestConfig",
        parameters={
            "test_param": StrategyParameter(
                name="test_param",
                type="int",
                required=True,
                default=1,
                display_name="Test Parameter",
                description="Test description",
                group=ParameterGroup.GENERAL,
                is_advanced=False,
                constraints=ParameterConstraints(),
                display_type=DisplayType.INPUT
            )
        }
    )

@pytest.mark.asyncio
async def test_discover_strategies():
    """Test strategy auto-discovery"""
    strategies = discover_strategies()
    
    # Verify we found some strategies
    assert len(strategies) > 0
    
    # Verify each strategy has the required fields
    for strategy_id, strategy in strategies.items():
        assert strategy.id == strategy_id
        assert strategy.display_name
        assert strategy.description
        assert strategy.strategy_type in [StrategyType.DIRECTIONAL_TRADING, StrategyType.MARKET_MAKING, StrategyType.GENERIC]
        assert strategy.module_path
        assert strategy.config_class
        assert strategy.parameters
        
        # Verify each parameter has the required fields
        for param_name, param in strategy.parameters.items():
            assert param.name == param_name
            assert param.type
            assert isinstance(param.required, bool)
            assert param.display_name
            assert param.description is not None  # Can be empty but should exist
            assert param.group in ParameterGroup
            assert isinstance(param.is_advanced, bool)
            assert param.display_type in DisplayType 