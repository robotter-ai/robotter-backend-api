import os
import json
import logging
import aiohttp
import inspect
import importlib
from typing import Dict, Any, List, Optional
from routers.strategies_models import (
    ParameterSuggestion,
    StrategyConfig,
    StrategyMapping,
    discover_strategies
)

logger = logging.getLogger(__name__)

class LibertAIService:
    def __init__(self):
        # Hermes 2 pro
        self.api_url = "https://curated.aleph.cloud/vm/84df52ac4466d121ef3bb409bb14f315de7be4ce600e8948d71df6485aa5bcc3/completion"
        
        self.strategy_slot_map: Dict[str, int] = {}  # Maps strategy IDs to their slot IDs
        self.next_slot_id = 0
        
    async def initialize_contexts(self, strategies: Dict[str, StrategyConfig]):
        """Initialize context slots for system prompt and each strategy."""
        try:
            logger.info("Starting context initialization...")
            
            # Initialize system prompt in slot -1
            logger.info("Initializing system context...")
            await self._initialize_system_context()
            
            # Initialize each strategy's context
            for strategy_id, strategy_config in strategies.items():
                logger.info(f"Initializing context for strategy: {strategy_id}")
                slot_id = self.next_slot_id
                self.strategy_slot_map[strategy_id] = slot_id
                self.next_slot_id += 1
                
                # Load strategy implementation code
                strategy_code = await self._load_strategy_code(strategy_config.mapping)
                logger.info(f"Loaded strategy code for {strategy_id}, code length: {len(strategy_code)}")
                
                await self._initialize_strategy_context(
                    strategy_mapping=strategy_config.mapping,
                    strategy_config=strategy_config.parameters,
                    strategy_code=strategy_code,
                    slot_id=slot_id
                )
                
            logger.info(f"Context initialization complete. Strategy slot map: {self.strategy_slot_map}")
            
        except Exception as e:
            logger.error(f"Error initializing contexts: {str(e)}")
            raise
    
    async def _load_strategy_code(self, mapping: StrategyMapping) -> str:
        """Load the strategy implementation code using the strategy mapping."""
        try:
            # Import the module using the mapping's module path
            module = importlib.import_module(mapping.module_path)
            
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
                raise ValueError(f"No strategy class found in {mapping.module_path}")
            
            # Get the source code of the strategy class
            strategy_class = strategy_classes[0][1]  # Take the first class
            source_code = inspect.getsource(strategy_class)
            
            return source_code
            
        except Exception as e:
            logger.error(f"Error loading strategy code for {mapping.id}: {str(e)}")
            return f"# Strategy implementation code not found for {mapping.id}"
    
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
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.api_url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "prompt": system_prompt,
                        "temperature": 0.9,
                        "top_p": 1,
                        "top_k": 40,
                        "n": 1,
                        "n_predict": 100,
                        "stop": ["<|im_end|>"]
                    }
                )
        except Exception as e:
            print(f"ERROR: Error initializing system context: {str(e)}")
            raise
    
    async def _initialize_strategy_context(
        self,
        strategy_mapping: StrategyMapping,
        strategy_config: Dict[str, Any],
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
                "prompt": param.prompt,
                "default": str(param.default) if param.default is not None else None,
                "required": param.required,
                "min_value": str(param.min_value) if param.min_value is not None else None,
                "max_value": str(param.max_value) if param.max_value is not None else None,
                "is_advanced": param.is_advanced,
                "display_type": param.display_type
            }
            for name, param in strategy_config.items()
        }

        strategy_context = f"""<|im_start|>user
Trading Strategy: {strategy_mapping.display_name}
Type: {strategy_mapping.strategy_type.value}
Description: {strategy_mapping.description}

Strategy Configuration Schema:
{json.dumps(serializable_config, indent=2)}

Strategy Implementation:
```python
{strategy_code}
```

This strategy's configuration defines the parameters and their constraints, while the implementation shows how these parameters are used in the trading logic. Use both to make informed suggestions about parameter values.
<|im_end|>"""

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.api_url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "prompt": strategy_context,
                        "temperature": 0.9,
                        "top_p": 1,
                        "top_k": 40,
                        "n": 1,
                        "n_predict": 100,
                        "stop": ["<|im_end|>"],
                        "slot_id": slot_id,
                        "parent_slot_id": -1,
                    }
                )
        except Exception as e:
            print(f"ERROR: Error initializing strategy context for {strategy_mapping.id}: {str(e)}")
            raise
        
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
        print("\n=== Getting Parameter Suggestions ===")
        print(f"Strategy ID: {strategy_id}")
        print(f"Provided parameters: {json.dumps(provided_params, indent=2)}")
        print(f"Requested parameters: {requested_params}")
        
        # Get strategy configuration
        strategies = discover_strategies()
        strategy = strategies.get(strategy_id)
        if not strategy:
            print(f"ERROR: No strategy found with ID {strategy_id}")
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
        
        print(f"Missing required parameters: {missing_required}")
        print(f"Optional parameters: {optional_params}")
        
        # Get the strategy's slot ID
        slot_id = self.strategy_slot_map.get(strategy_id)
        if slot_id is None:
            print(f"ERROR: No cached context found for strategy {strategy_id}")
            return []
        
        # Convert parameters to a serializable format
        serializable_params = {
            name: str(value) if hasattr(value, "__str__") else value
            for name, value in provided_params.items()
        }
        
        # Update the prompt to be more explicit about the format and requested parameters
        optional_params_text = f"Optional Parameters That Could Be Set:\n{', '.join(optional_params) if optional_params else 'None'}" if not requested_params else ""

        request_prompt = f"""<|im_start|>user
Strategy: {strategy.mapping.display_name}
Type: {strategy.mapping.strategy_type.value}

Currently Provided Parameters:
{json.dumps(serializable_params, indent=2)}

{"Parameters to Suggest:" if requested_params else "Missing Required Parameters:"}
{', '.join(requested_params) if requested_params else ', '.join(missing_required) if missing_required else 'None'}

{optional_params_text}

Please suggest optimal values for {"the requested" if requested_params else "the missing"} parameters using exactly this format for each parameter:

PARAMETER: [parameter_name]
VALUE: [suggested_value]
REASONING: [detailed explanation of why this value is appropriate]

End with a summary:
SUMMARY: [overall explanation of the suggested configuration]

Do not include code blocks or other formats. Use only the PARAMETER/VALUE/REASONING structure.
<|im_end|>"""

        try:
            async with aiohttp.ClientSession() as session:
                print(f"\nSending request to LibertAI API...")
                print(f"Request prompt:\n{request_prompt}")
                
                request_payload = {
                    "slot_id": self.next_slot_id,
                    "parent_slot_id": slot_id,
                    "prompt": request_prompt,
                    "temperature": 0.9,
                    "top_p": 1,
                    "top_k": 40,
                    "n": 1,
                    "n_predict": 1500,
                    "stop": ["<|im_end|>"]
                }
                
                async with session.post(
                    self.api_url,
                    headers={"Content-Type": "application/json"},
                    json=request_payload
                ) as response:
                    if response.status != 200:
                        print(f"ERROR: API returned status {response.status}")
                        response_text = await response.text()
                        print(f"Response body: {response_text}")
                        return []
                    
                    result = await response.json()
                    print(f"\nReceived response from API: {json.dumps(result, indent=2)}")
                    return self._parse_ai_response(
                        {"choices": [{"message": {"content": result["content"]}}]},
                        strategy_config=strategy_config,
                        provided_params=provided_params
                    )
                    
        except Exception as e:
            print(f"ERROR: Exception during API call: {str(e)}")
            return []
    
    def _parse_ai_response(self, ai_response: Dict[str, Any], strategy_config: Dict[str, Any], provided_params: Dict[str, Any]) -> List[ParameterSuggestion]:
        print("\n=== Parsing AI Response ===")
        try:
            content = ai_response["choices"][0]["message"]["content"]
            print(f"Response content preview: {content[:200]}...")
            
            suggestions = []
            seen_params = set()
            summary = None
            
            # Create a map of default values and provided values for comparison
            default_values = {
                name: str(param.default) if param.default is not None else None
                for name, param in strategy_config.items()
            }
            
            provided_values = {
                name: str(value) if hasattr(value, "__str__") else str(value)
                for name, value in provided_params.items()
            }
            
            if "PARAMETER:" in content:
                print("Found structured format with PARAMETER/VALUE/REASONING")
                parameter_sections = content.split("PARAMETER:")
                
                for section in parameter_sections[1:]:
                    lines = section.strip().split("\n")
                    param_name = lines[0].strip()
                    
                    # Initialize collectors for multi-line values
                    value_lines = []
                    reasoning_lines = []
                    collecting_value = False
                    collecting_reasoning = False
                    
                    # Process remaining lines
                    for line in lines[1:]:
                        line = line.strip()
                        
                        if line.startswith("VALUE:"):
                            collecting_value = True
                            collecting_reasoning = False
                            value_lines.append(line.replace("VALUE:", "").strip())
                        elif line.startswith("REASONING:"):
                            collecting_value = False
                            collecting_reasoning = True
                            reasoning_lines.append(line.replace("REASONING:", "").strip())
                        elif line.startswith("SUMMARY:"):
                            collecting_value = False
                            collecting_reasoning = False
                            summary = line.replace("SUMMARY:", "").strip()
                        else:
                            # Continue collecting multi-line values
                            if collecting_value and line:
                                value_lines.append(line)
                            elif collecting_reasoning and line:
                                reasoning_lines.append(line)
                    
                    # Process collected values
                    if param_name and value_lines and param_name not in seen_params:
                        seen_params.add(param_name)
                        
                        # Join multi-line values and try to parse as JSON if it looks like a JSON structure
                        value = "\n".join(value_lines)
                        if value.strip().startswith("{") and value.strip().endswith("}"):
                            try:
                                parsed_value = json.loads(value)
                                value = json.dumps(parsed_value)
                            except json.JSONDecodeError:
                                pass
                        
                        # Compare with default and provided values
                        differs_from_default = (
                            param_name in default_values and 
                            default_values[param_name] is not None and 
                            value != default_values[param_name]
                        )
                        differs_from_provided = (
                            param_name in provided_values and 
                            value != provided_values[param_name]
                        )
                        
                        suggestions.append(ParameterSuggestion(
                            parameter_name=param_name,
                            suggested_value=value,
                            reasoning="\n".join(reasoning_lines) if reasoning_lines else "No reasoning provided",
                            differs_from_default=differs_from_default,
                            differs_from_provided=differs_from_provided
                        ))
            
            if summary:
                suggestions.append(ParameterSuggestion(
                    parameter_name="summary",
                    suggested_value=summary,
                    reasoning="Summary of the suggested configuration",
                    differs_from_default=False,
                    differs_from_provided=False
                ))
            
            print(f"\nTotal suggestions parsed: {len(suggestions)}")
            for s in suggestions:
                print(f"- {s.parameter_name}: {s.suggested_value}")
                if s.differs_from_default:
                    print(f"  (differs from default: {s.differs_from_default})")
                if s.differs_from_provided:
                    print(f"  (differs from provided: {s.differs_from_provided})")
            
            return suggestions
            
        except Exception as e:
            print(f"ERROR: Failed to parse AI response: {str(e)}")
            print(f"Raw response: {json.dumps(ai_response, indent=2)}")
            return [] 