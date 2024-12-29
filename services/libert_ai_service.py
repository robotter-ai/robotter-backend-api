import json
import logging
import aiohttp
import inspect
import importlib
from typing import Dict, Any, List, Optional, Protocol
from routers.strategies_models import (
    ParameterSuggestion,
    StrategyConfig,
    StrategyMapping,
    discover_strategies
)

logger = logging.getLogger(__name__)

class AIClient(Protocol):
    """Protocol for AI client implementations"""
    async def initialize_system_context(self, prompt: str) -> Dict[str, Any]:
        """Initialize system context with the given prompt"""
        ...

    async def initialize_strategy_context(self, prompt: str, slot_id: int) -> Dict[str, Any]:
        """Initialize strategy context with the given prompt"""
        ...

    async def get_suggestions(self, prompt: str, slot_id: int) -> Dict[str, Any]:
        """Get suggestions from the AI model"""
        ...

class LibertAIClient:
    """Default implementation of AIClient using Libert API"""
    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or "https://curated.aleph.cloud/vm/84df52ac4466d121ef3bb409bb14f315de7be4ce600e8948d71df6485aa5bcc3/completion"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure we have an active session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _make_api_request(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make the actual API request. This is the only method that should make HTTP calls."""
        session = await self._ensure_session()
        async with session.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload
        ) as response:
            if response.status != 200:
                raise ValueError(f"API request failed with status {response.status}")
            return await response.json()

    def _build_request_payload(
        self, 
        prompt: str, 
        slot_id: Optional[int] = None, 
        parent_slot_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Build the request payload with all necessary parameters."""
        payload = {
            "prompt": prompt,
            "temperature": 0.9,
            "top_p": 1,
            "top_k": 40,
            "n": 1,
            "n_predict": 100,
            "stop": ["<|im_end|>"]
        }
        if slot_id is not None:
            payload["slot_id"] = slot_id
        if parent_slot_id is not None:
            payload["parent_slot_id"] = parent_slot_id
        return payload

    async def _make_request(self, prompt: str, slot_id: Optional[int] = None, parent_slot_id: Optional[int] = None) -> Dict[str, Any]:
        """Make a request to the AI API"""
        payload = self._build_request_payload(prompt, slot_id, parent_slot_id)
        return await self._make_api_request(self.api_url, payload)

    async def initialize_system_context(self, prompt: str) -> Dict[str, Any]:
        """Initialize system context with the given prompt"""
        return await self._make_request(prompt)

    async def initialize_strategy_context(self, prompt: str, slot_id: int) -> Dict[str, Any]:
        """Initialize strategy context with the given prompt"""
        return await self._make_request(prompt, slot_id=slot_id, parent_slot_id=-1)

    async def get_suggestions(self, prompt: str, slot_id: int) -> Dict[str, Any]:
        """Get suggestions from the AI model"""
        return await self._make_request(prompt, slot_id=slot_id)

    async def close(self):
        """Close the client session"""
        if self.session:
            await self.session.close()
            self.session = None

class LibertAIService:
    def __init__(self, ai_client: Optional[AIClient] = None):
        self.ai_client = ai_client or LibertAIClient()
        self.strategy_slot_map: Dict[str, int] = {}  # Maps strategy IDs to their slot IDs
        self.next_slot_id = 0

    async def _initialize_system_context(self):
        """Initialize the system prompt in slot -1."""
        system_prompt = """<|im_start|>system
You are an expert trading strategy advisor. Your task is to analyze trading strategies and suggest optimal parameter values.

For each parameter suggestion, you must:
1. Suggest an appropriate value based on the strategy type and configuration
2. Provide a clear explanation of why this value would be appropriate
3. Consider potential risks and market conditions
4. Take into account the strategy's implementation code and logic

Format each suggestion exactly as follows:
PARAMETER: [parameter_name]
VALUE: [suggested_value]
REASONING: [detailed explanation]
<|im_end|>"""

        try:
            await self.ai_client.initialize_system_context(system_prompt)
        except Exception as e:
            logger.error(f"Error initializing system context: {str(e)}")
            raise

    async def _initialize_strategy_context(
        self,
        strategy: StrategyMapping,
        strategy_code: str,
        slot_id: int
    ):
        """Initialize context for a specific strategy."""
        # Convert strategy parameters to a serializable format
        serializable_config = {
            name: {
                "name": param.name,
                "group": param.group,
                "type": param.type,
                "default": str(param.default) if param.default is not None else None,
                "required": param.required,
                "min_value": str(param.constraints.min_value) if param.constraints and param.constraints.min_value is not None else None,
                "max_value": str(param.constraints.max_value) if param.constraints and param.constraints.max_value is not None else None,
                "is_advanced": param.is_advanced,
                "display_type": param.display_type
            }
            for name, param in strategy.parameters.items()
        }

        strategy_context = f"""<|im_start|>user
Trading Strategy: {strategy.display_name}
Type: {strategy.strategy_type.value}
Description: {strategy.description}

Strategy Configuration Schema:
{json.dumps(serializable_config, indent=2)}

Strategy Implementation:
```python
{strategy_code}
```

This strategy's configuration defines the parameters and their constraints, while the implementation shows how these parameters are used in the trading logic. Use both to make informed suggestions about parameter values.
<|im_end|>"""

        try:
            await self.ai_client.initialize_strategy_context(strategy_context, slot_id)
        except Exception as e:
            logger.error(f"Error initializing strategy context for {strategy.id}: {str(e)}")
            raise
        
    async def initialize_contexts(self, strategies: Dict[str, StrategyMapping]):
        """Initialize context slots for system prompt and each strategy."""
        try:
            logger.info("Starting context initialization...")
            
            # Initialize system prompt in slot -1
            logger.info("Initializing system context...")
            await self._initialize_system_context()
            
            # Initialize each strategy's context
            for strategy_id, strategy in strategies.items():
                logger.info(f"Initializing context for strategy: {strategy_id}")
                slot_id = self.next_slot_id
                self.strategy_slot_map[strategy_id] = slot_id
                self.next_slot_id += 1
                
                # Load strategy implementation code
                strategy_code = await self._load_strategy_code(strategy)
                logger.info(f"Loaded strategy code for {strategy_id}, code length: {len(strategy_code)}")
                
                await self._initialize_strategy_context(
                    strategy=strategy,
                    strategy_code=strategy_code,
                    slot_id=slot_id
                )
                
            logger.info(f"Context initialization complete. Strategy slot map: {self.strategy_slot_map}")
            
        except Exception as e:
            logger.error(f"Error initializing contexts: {str(e)}")
            raise
    
    async def _load_strategy_code(self, strategy: StrategyMapping) -> str:
        """Load the strategy implementation code using the strategy mapping."""
        try:
            # Import the module using the mapping's module path
            module = importlib.import_module(strategy.module_path)
            
            # Get all classes in the module
            strategy_classes = inspect.getmembers(
                module,
                lambda member: (
                    inspect.isclass(member) 
                    and member.__module__ == module.__name__
                    and not member.__name__.endswith('Config')
                )
            )
            
            if not strategy_classes:
                raise ValueError(f"No strategy class found in {strategy.module_path}")
            
            # Get the source code of the strategy class
            strategy_class = strategy_classes[0][1]  # Take the first class
            source_code = inspect.getsource(strategy_class)
            
            return source_code
            
        except Exception as e:
            logger.error(f"Error loading strategy code for {strategy.id}: {str(e)}")
            return f"# Strategy implementation code not found for {strategy.id}"
        
    async def get_parameter_suggestions(
        self,
        strategy_id: str,
        strategy_config: Dict[str, Any],
        provided_params: Dict[str, Any],
        requested_params: Optional[List[str]] = None
    ) -> List[ParameterSuggestion]:
        """Get parameter suggestions from LibertAI.
        
        Args:
            strategy_id: ID of the strategy
            strategy_config: Full strategy configuration
            provided_params: Parameters already provided by the user
            requested_params: Optional list of specific parameters to get suggestions for
        """
        logger.info("\n=== Getting Parameter Suggestions ===")
        logger.info(f"Strategy ID: {strategy_id}")
        logger.info(f"Provided parameters: {json.dumps(provided_params, indent=2)}")
        logger.info(f"Requested parameters: {requested_params}")
        
        # Get strategy configuration
        strategies = discover_strategies()
        strategy = strategies.get(strategy_id)
        if not strategy:
            logger.error(f"No strategy found with ID {strategy_id}")
            return []
        
        # Identify missing required parameters and optional parameters
        missing_required = []
        optional_params = []
        
        # If specific parameters are requested, only consider those
        params_to_check = requested_params if requested_params else strategy_config.keys()
        
        for param_name in params_to_check:
            if param_name not in provided_params:
                param_config = strategy_config.get(param_name)
                if param_config:
                    if param_config.required:
                        missing_required.append(param_name)
                    else:
                        optional_params.append(param_name)
        
        logger.info(f"Missing required parameters: {missing_required}")
        logger.info(f"Optional parameters: {optional_params}")
        
        # Get the strategy's slot ID
        slot_id = self.strategy_slot_map.get(strategy_id)
        if slot_id is None:
            logger.error(f"No cached context found for strategy {strategy_id}")
            return []
        
        # Convert parameters to a serializable format
        serializable_params = {
            name: str(value) if hasattr(value, "__str__") else value
            for name, value in provided_params.items()
        }
        
        # Update the prompt to be more explicit about the format and requested parameters
        optional_params_text = f"Optional Parameters That Could Be Set:\n{', '.join(optional_params) if optional_params else 'None'}" if not requested_params else ""
        
        request_prompt = f"""<|im_start|>user
>   Strategy: {strategy.display_name}
    Type: {strategy.strategy_type.value}
    
    Currently Provided Parameters:
    {json.dumps(serializable_params, indent=2)}
    
    Parameters Requiring Suggestions:
    {', '.join(missing_required) if missing_required else 'None'}
    
    {optional_params_text}
    
    Please suggest values for the missing required parameters and any optional parameters that would improve the strategy's performance.
    <|im_end|>"""

        try:
            response = await self.ai_client.get_suggestions(request_prompt, slot_id)
            suggestions = self._parse_ai_response(response, strategy_config, provided_params)
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting parameter suggestions: {str(e)}")
            return []
    
    def _parse_ai_response(
        self,
        ai_response: Dict[str, Any],
        strategy_config: Dict[str, Any],
        provided_params: Dict[str, Any]
    ) -> List[ParameterSuggestion]:
        """Parse the AI response and extract parameter suggestions."""
        suggestions = []
        summary_suggestion = None
        
        try:
            # Extract the response content
            content = ai_response.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return []
            
            # Split the content into sections
            sections = content.strip().split("\n\n")
            
            # Process each section
            current_param = None
            current_value = None
            current_reasoning = None
            
            for section in sections:
                lines = section.strip().split("\n")
                for line in lines:
                    if line.startswith("PARAMETER:"):
                        # If we have a complete suggestion, add it
                        if current_param and current_value is not None:
                            param_config = strategy_config.get(current_param)
                            if param_config:
                                suggestion = ParameterSuggestion(
                                    parameter_name=current_param,
                                    suggested_value=current_value,
                                    reasoning=current_reasoning or "",
                                    differs_from_default=str(current_value) != str(param_config.default),
                                    differs_from_provided=current_param in provided_params and str(current_value) != str(provided_params[current_param])
                                )
                                suggestions.append(suggestion)
                        
                        # Start a new suggestion
                        current_param = line.replace("PARAMETER:", "").strip()
                        current_value = None
                        current_reasoning = None
                        
                    elif line.startswith("VALUE:"):
                        current_value = line.replace("VALUE:", "").strip()
                        
                    elif line.startswith("REASONING:"):
                        current_reasoning = line.replace("REASONING:", "").strip()
                        
                    elif line.startswith("SUMMARY:"):
                        # Create a summary suggestion
                        summary_value = line.replace("SUMMARY:", "").strip()
                        if summary_value:
                            summary_suggestion = ParameterSuggestion(
                                parameter_name="summary",
                                suggested_value=summary_value,
                                reasoning="Overall summary of suggestions",
                                differs_from_default=False,
                                differs_from_provided=False
                            )
                    
                    elif current_reasoning is not None:
                        # Append additional reasoning lines
                        current_reasoning += " " + line.strip()
            
            # Add the last suggestion if complete
            if current_param and current_value is not None:
                param_config = strategy_config.get(current_param)
                if param_config:
                    suggestion = ParameterSuggestion(
                        parameter_name=current_param,
                        suggested_value=current_value,
                        reasoning=current_reasoning or "",
                        differs_from_default=str(current_value) != str(param_config.default),
                        differs_from_provided=current_param in provided_params and str(current_value) != str(provided_params[current_param])
                    )
                    suggestions.append(suggestion)
            
            # Add the summary suggestion at the end if we have one
            if summary_suggestion:
                suggestions.append(summary_suggestion)
            
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            
        return suggestions

    async def close(self):
        """Close the AI client."""
        if isinstance(self.ai_client, LibertAIClient):
            await self.ai_client.close() 