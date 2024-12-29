import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.libert_ai_service import LibertAIService, LibertAIClient
from routers.strategies_models import (
    StrategyMapping,
    StrategyType,
    StrategyParameter,
    ParameterConstraints,
    ParameterGroup,
    DisplayType
)

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_ai_client():
    return AsyncMock(spec=LibertAIClient)

@pytest.fixture
def service(mock_ai_client):
    return LibertAIService(mock_ai_client)

async def test_initialize_system_context(service, mock_ai_client):
    """Test successful system context initialization"""
    await service._initialize_system_context()
    mock_ai_client.initialize_system_context.assert_called_once()

async def test_initialize_system_context_error(service, mock_ai_client):
    """Test error handling in system context initialization"""
    mock_ai_client.initialize_system_context.side_effect = ValueError("API Error")
    
    with pytest.raises(ValueError, match="API Error"):
        await service._initialize_system_context()

async def test_load_strategy_code_success(service):
    """Test successful strategy code loading"""
    mapping = StrategyMapping(
        id="test_strategy",
        display_name="Test Strategy",
        module_path="tests.unit.fixtures.test_strategy",
        strategy_type=StrategyType.DIRECTIONAL_TRADING,
        config_class="TestConfig"
    )
    
    with patch('importlib.import_module') as mock_import:
        mock_module = MagicMock(spec=['__name__'])
        mock_class = MagicMock(spec=['__module__'])
        mock_module.__name__ = mapping.module_path
        mock_class.__module__ = mapping.module_path
        mock_import.return_value = mock_module
        
        # Mock inspect.getmembers to return our mock class
        with patch('inspect.getmembers', return_value=[('TestStrategy', mock_class)]):
            # Mock inspect.getsource to return some test code
            test_code = "class TestStrategy:\n    pass"
            with patch('inspect.getsource', return_value=test_code):
                result = await service._load_strategy_code(mapping)
                assert result == test_code

async def test_load_strategy_code_import_error(service):
    """Test error handling when strategy module cannot be imported"""
    mapping = StrategyMapping(
        id="test_strategy",
        display_name="Test Strategy",
        module_path="nonexistent.module",
        strategy_type=StrategyType.DIRECTIONAL_TRADING,
        config_class="TestConfig"
    )
    
    with patch('importlib.import_module', side_effect=ImportError("Module not found")):
        result = await service._load_strategy_code(mapping)
        assert "Strategy implementation code not found" in result

async def test_load_strategy_code_no_class(service):
    """Test error handling when no strategy class is found"""
    mapping = StrategyMapping(
        id="test_strategy",
        display_name="Test Strategy",
        module_path="tests.unit.fixtures.test_strategy",
        strategy_type=StrategyType.DIRECTIONAL_TRADING,
        config_class="TestConfig"
    )
    
    with patch('importlib.import_module') as mock_import:
        mock_module = MagicMock(spec=['__name__'])
        mock_module.__name__ = mapping.module_path
        mock_import.return_value = mock_module
        
        # Mock inspect.getmembers to return an empty list (no classes found)
        with patch('inspect.getmembers', return_value=[]):
            result = await service._load_strategy_code(mapping)
            assert "Strategy implementation code not found" in result

async def test_initialize_strategy_context_error(service, mock_ai_client):
    """Test error handling in strategy context initialization"""
    strategy = StrategyMapping(
        id="test_strategy",
        display_name="Test Strategy",
        module_path="test.module",
        strategy_type=StrategyType.DIRECTIONAL_TRADING,
        config_class="TestConfig",
        description="Test strategy",
        parameters={
            "param1": StrategyParameter(
                name="param1",
                type="int",
                default=1,
                required=True,
                display_name="Parameter 1",
                description="Test parameter",
                group=ParameterGroup.GENERAL,
                is_advanced=False,
                constraints=ParameterConstraints(),
                display_type=DisplayType.INPUT
            )
        }
    )

    mock_ai_client.initialize_strategy_context.side_effect = ValueError("API Error")

    with pytest.raises(ValueError, match="API Error"):
        await service._initialize_strategy_context(
            strategy=strategy,
            strategy_code="class TestStrategy: pass",
            slot_id=1
        )

async def test_initialize_contexts_error(service, mock_ai_client):
    """Test error handling in contexts initialization"""
    strategies = {
        "test_strategy": MagicMock(
            mapping=StrategyMapping(
                id="test_strategy",
                display_name="Test Strategy",
                module_path="test.module",
                strategy_type=StrategyType.DIRECTIONAL_TRADING,
                config_class="TestConfig"
            ),
            parameters={}
        )
    }
    
    mock_ai_client.initialize_system_context.side_effect = ValueError("API Error")
    
    with pytest.raises(ValueError, match="API Error"):
        await service.initialize_contexts(strategies)

async def test_get_parameter_suggestions_no_strategy(service):
    """Test error handling when strategy is not found"""
    result = await service.get_parameter_suggestions(
        strategy_id="nonexistent",
        strategy_config={},
        provided_params={}
    )
    assert result == []

async def test_get_parameter_suggestions_no_slot(service):
    """Test error handling when no slot is found for strategy"""
    with patch('routers.strategies_models.discover_strategies') as mock_discover:
        mock_discover.return_value = {
            "test_strategy": MagicMock()
        }
        
        result = await service.get_parameter_suggestions(
            strategy_id="test_strategy",
            strategy_config={},
            provided_params={}
        )
        assert result == []

async def test_get_parameter_suggestions_api_error(service, mock_ai_client):
    """Test error handling when AI API call fails"""
    service.strategy_slot_map = {"test_strategy": 1}
    
    with patch('routers.strategies_models.discover_strategies') as mock_discover:
        mock_discover.return_value = {
            "test_strategy": MagicMock(
                mapping=MagicMock(
                    display_name="Test Strategy",
                    strategy_type=StrategyType.DIRECTIONAL_TRADING
                )
            )
        }
        
        mock_ai_client.get_suggestions.side_effect = ValueError("API Error")
        
        result = await service.get_parameter_suggestions(
            strategy_id="test_strategy",
            strategy_config={},
            provided_params={}
        )
        assert result == [] 