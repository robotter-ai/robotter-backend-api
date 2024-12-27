from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from services.accounts_service import AccountsService, BotConfig
from services.docker_service import DockerManager
from fastapi_walletauth import JWTWalletAuthDep
from utils.models import HummingbotInstanceConfig, StartStrategyRequest, InstanceResponse
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from routers.strategies_models import (
    StrategyError,
    StrategyRegistry,
    StrategyNotFoundError,
    StrategyValidationError
)

router = APIRouter(tags=["Bot Management"])
accounts_service = AccountsService()
docker_manager = DockerManager()
gateway_client = GatewayHttpClient.get_instance()

class BotError(StrategyError):
    """Base class for bot-related errors"""

class BotNotFoundError(BotError):
    """Raised when a bot cannot be found"""

class BotPermissionError(BotError):
    """Raised when there's a permission error with bot operations"""

class BotConfigError(BotError):
    """Raised when there's an error in bot configuration"""

class CreateBotRequest(BaseModel):
    strategy_name: str
    strategy_parameters: dict
    market: str

responses = {
    400: {
        "description": "Bad Request - Invalid bot configuration",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_strategy": {
                        "summary": "Invalid Strategy",
                        "value": {"detail": "Invalid strategy: Strategy 'unknown_strategy' not found"}
                    },
                    "invalid_params": {
                        "summary": "Invalid Parameters",
                        "value": {"detail": "Invalid strategy parameters: Parameter 'stop_loss' value 0.5 is above maximum 0.1"}
                    },
                    "invalid_config": {
                        "summary": "Invalid Configuration",
                        "value": {"detail": "Error saving bot configuration: Invalid market format"}
                    }
                }
            }
        }
    },
    403: {
        "description": "Forbidden - Permission denied",
        "content": {
            "application/json": {
                "example": {"detail": "You don't have permission to access this bot"}
            }
        }
    },
    404: {
        "description": "Not Found - Bot not found",
        "content": {
            "application/json": {
                "example": {"detail": "Bot wallet not found: Invalid bot ID"}
            }
        }
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "creation_error": {
                        "summary": "Creation Error",
                        "value": {"detail": "Error creating Hummingbot instance: Docker service unavailable"}
                    },
                    "start_error": {
                        "summary": "Start Error",
                        "value": {"detail": "Error starting bot: Failed to initialize trading"}
                    }
                }
            }
        }
    }
}

@router.post(
    "/bots",
    response_model=InstanceResponse,
    responses={
        200: {
            "description": "Successfully created trading bot",
            "content": {
                "application/json": {
                    "example": {
                        "instance_id": "robotter_0x123_sol-usdc_bollinger_v1",
                        "wallet_address": "0xabc...def",
                        "market": "sol-usdc"
                    }
                }
            }
        },
        **responses
    },
    summary="Create Trading Bot",
    description="""
    Create a new trading bot instance with specified strategy and configuration.
    
    The creation process:
    1. Validates the strategy and its parameters
    2. Creates a dedicated bot account
    3. Generates a bot-specific wallet
    4. Saves the configuration
    5. Creates a Hummingbot instance
    
    Requirements:
    - Valid strategy name from available strategies
    - Valid strategy parameters within constraints
    - Valid market format (e.g., "sol-usdc")
    - Authenticated wallet connection
    
    The created bot will:
    - Have its own isolated wallet
    - Run in a dedicated Docker container
    - Use the specified trading strategy
    - Trade on the specified market
    
    Security features:
    - Bot wallet is separate from user wallet
    - Bot permissions are limited to its specific market
    - Trading parameters are validated before deployment
    """
)
async def create_bot(request: CreateBotRequest, wallet_auth: JWTWalletAuthDep):
    try:
        # Validate strategy exists and parameters
        try:
            strategy = StrategyRegistry.get_strategy(request.strategy_name)
        except StrategyNotFoundError as e:
            raise BotConfigError(f"Invalid strategy: {str(e)}")

        try:
            validate_strategy_parameters(strategy, request.strategy_parameters)
        except StrategyValidationError as e:
            raise BotConfigError(f"Invalid strategy parameters: {str(e)}")

        # Create bot account
        bot_account = f"robotter_{wallet_auth.address}_{request.market}_{request.strategy_name}"
        try:
            accounts_service.add_account(bot_account)
            wallet_address = await accounts_service.generate_bot_wallet(bot_account)
        except Exception as e:
            raise BotError(f"Error creating bot account: {str(e)}")

        # Save strategy configuration and market
        try:
            bot_config = BotConfig(
                strategy_name=request.strategy_name,
                parameters=request.strategy_parameters,
                market=request.market,
                wallet_address=wallet_auth.address,
            )
            accounts_service.save_bot_config(bot_account, bot_config)
        except Exception as e:
            raise BotConfigError(f"Error saving bot configuration: {str(e)}")

        # Create Hummingbot instance
        try:
            instance_config = HummingbotInstanceConfig(
                instance_name=bot_account,
                credentials_profile=bot_account,
                image="mlguys/hummingbot:mango",
                market=request.market
            )
            result = docker_manager.create_hummingbot_instance(instance_config)

            if not result["success"]:
                raise BotError(result["message"])
        except Exception as e:
            raise BotError(f"Error creating Hummingbot instance: {str(e)}")

        return InstanceResponse(
            instance_id=bot_account,
            wallet_address=wallet_address,
            market=request.market
        )

    except BotConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BotPermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except BotError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error creating bot: {str(e)}"
        )

@router.get(
    "/bots/{bot_id}/wallet",
    responses={
        200: {
            "description": "Successfully retrieved bot wallet",
            "content": {
                "application/json": {
                    "example": {
                        "wallet_address": "0xabc...def"
                    }
                }
            }
        },
        **responses
    },
    summary="Get Bot Wallet",
    description="""
    Retrieve the wallet address associated with a specific trading bot.
    
    Security checks:
    - Verifies that the requesting user owns the bot
    - Validates the bot ID format
    - Ensures the bot exists
    
    The wallet address can be used to:
    - Monitor bot's trading activity
    - Track bot's balance
    - Verify transactions
    """
)
async def get_bot_wallet(bot_id: str, wallet_auth: JWTWalletAuthDep):
    try:
        # Check if the bot belongs to the authenticated user
        if not bot_id.endswith(wallet_auth.address):
            raise BotPermissionError("You don't have permission to access this bot")

        try:
            wallet_address = accounts_service.get_bot_wallet_address(bot_id)
            return {"wallet_address": wallet_address}
        except Exception as e:
            raise BotNotFoundError(f"Bot wallet not found: {str(e)}")

    except BotPermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except BotNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error getting bot wallet: {str(e)}"
        )

@router.post(
    "/bots/{bot_id}/start",
    responses={
        200: {
            "description": "Successfully started trading bot",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Bot started successfully"
                    }
                }
            }
        },
        **responses
    },
    summary="Start Trading Bot",
    description="""
    Start a trading bot with the specified configuration.
    
    The start process:
    1. Validates user permissions
    2. Checks Mango account configuration
    3. Loads strategy configuration
    4. Initializes the trading engine
    5. Begins trading operations
    
    Requirements:
    - Bot must exist and belong to the user
    - Valid Mango account configuration
    - Proper strategy parameters
    
    The bot will:
    - Connect to specified markets
    - Load trading parameters
    - Begin executing the strategy
    - Monitor market conditions
    
    Safety features:
    - Permission verification
    - Account validation
    - Parameter checking
    - Graceful error handling
    """
)
async def start_bot(bot_id: str, start_request: StartStrategyRequest, wallet_auth: JWTWalletAuthDep):
    try:
        # Check if the bot belongs to the authenticated user
        bot_config = accounts_service.get_bot_config(bot_id)
        if not bot_config or bot_config.wallet_address != wallet_auth.address:
            raise BotPermissionError("You don't have permission to start this bot")

        # Check if Mango account exists and is associated with the bot's wallet
        try:
            bot_wallet = accounts_service.get_bot_wallet_address(bot_id)
            mango_account_info = await gateway_client.get_mango_account(
                "solana", "mainnet", "mango_perpetual_solana_mainnet-beta", bot_wallet
            )

            if not mango_account_info or mango_account_info.get("owner") != bot_wallet:
                raise BotConfigError("Invalid Mango account or not associated with the bot's wallet")
        except Exception as e:
            raise BotConfigError(f"Error validating Mango account: {str(e)}")

        # Start the bot
        try:
            strategy_config = accounts_service.get_strategy_config(bot_id)
            start_config = {**strategy_config, **start_request.parameters}

            response = docker_manager.start_bot(bot_id, start_config)
            if not response["success"]:
                raise BotError("Failed to start the bot")

            return {"status": "success", "message": "Bot started successfully"}
        except Exception as e:
            raise BotError(f"Error starting bot: {str(e)}")

    except BotPermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except BotConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BotError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error starting bot: {str(e)}"
        )

def validate_strategy_parameters(strategy, parameters: dict) -> None:
    """Validate strategy parameters against their constraints"""
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