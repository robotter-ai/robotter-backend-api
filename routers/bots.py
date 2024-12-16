from fastapi import APIRouter, HTTPException
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

@router.post("/bots", response_model=InstanceResponse)
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
        raise HTTPException(status_code=400, detail=str(e))
    except BotPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BotError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error creating bot: {str(e)}"
        )

@router.get("/bots/{bot_id}/wallet")
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
        raise HTTPException(status_code=403, detail=str(e))
    except BotNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error getting bot wallet: {str(e)}"
        )

@router.post("/bots/{bot_id}/start")
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
        raise HTTPException(status_code=403, detail=str(e))
    except BotConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BotError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
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