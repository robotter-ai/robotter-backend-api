import pytest
from unittest.mock import AsyncMock, patch
from services.libert_ai_service import LibertAIClient
from typing import Dict, Any

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_api_response():
    return {"content": "Test response"}

@pytest.fixture
def client():
    return LibertAIClient(api_url="http://test.api")

async def test_build_request_payload(client):
    """Test payload construction with different parameters"""
    # Test basic payload
    payload = client._build_request_payload("test prompt")
    assert payload["prompt"] == "test prompt"
    assert payload["temperature"] == 0.9
    assert payload["top_p"] == 1
    assert payload["top_k"] == 40
    assert payload["n"] == 1
    assert payload["n_predict"] == 100
    assert payload["stop"] == ["<|im_end|>"]
    assert "slot_id" not in payload
    assert "parent_slot_id" not in payload

    # Test with slot_id
    payload = client._build_request_payload("test prompt", slot_id=1)
    assert payload["slot_id"] == 1
    assert "parent_slot_id" not in payload

    # Test with both slot_id and parent_slot_id
    payload = client._build_request_payload("test prompt", slot_id=1, parent_slot_id=0)
    assert payload["slot_id"] == 1
    assert payload["parent_slot_id"] == 0

async def test_initialize_system_context(client, mock_api_response):
    """Test system context initialization"""
    with patch.object(client, '_make_api_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response
        
        response = await client.initialize_system_context("test prompt")
        
        assert response == mock_api_response
        mock_request.assert_called_once()
        call_args = mock_request.call_args[0]
        assert call_args[0] == "http://test.api"  # URL
        assert call_args[1]["prompt"] == "test prompt"  # Payload
        assert "slot_id" not in call_args[1]
        assert "parent_slot_id" not in call_args[1]

async def test_initialize_strategy_context(client, mock_api_response):
    """Test strategy context initialization"""
    with patch.object(client, '_make_api_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response
        
        response = await client.initialize_strategy_context("test prompt", slot_id=1)
        
        assert response == mock_api_response
        mock_request.assert_called_once()
        call_args = mock_request.call_args[0]
        assert call_args[0] == "http://test.api"  # URL
        assert call_args[1]["prompt"] == "test prompt"  # Payload
        assert call_args[1]["slot_id"] == 1
        assert call_args[1]["parent_slot_id"] == -1

async def test_get_suggestions(client, mock_api_response):
    """Test getting suggestions"""
    with patch.object(client, '_make_api_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response
        
        response = await client.get_suggestions("test prompt", slot_id=1)
        
        assert response == mock_api_response
        mock_request.assert_called_once()
        call_args = mock_request.call_args[0]
        assert call_args[0] == "http://test.api"  # URL
        assert call_args[1]["prompt"] == "test prompt"  # Payload
        assert call_args[1]["slot_id"] == 1
        assert "parent_slot_id" not in call_args[1]

async def test_session_management(client):
    """Test session creation and cleanup"""
    # Test session creation
    session = await client._ensure_session()
    assert session is not None
    assert client.session is session
    
    # Test session reuse
    session2 = await client._ensure_session()
    assert session2 is session
    
    # Test session cleanup
    await client.close()
    assert client.session is None

async def test_api_request_error_handling(client):
    """Test error handling in API requests"""
    with patch.object(client, '_make_api_request', new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = ValueError("API request failed with status 404")
        
        with pytest.raises(ValueError, match="API request failed with status 404"):
            await client.get_suggestions("test prompt", slot_id=1)
        
        mock_request.assert_called_once()
        call_args = mock_request.call_args[0]
        assert call_args[0] == "http://test.api"  # URL
        assert call_args[1]["prompt"] == "test prompt"  # Payload
        assert call_args[1]["slot_id"] == 1 