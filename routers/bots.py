from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.accounts_service import AccountsService, BotConfig
from services.docker_service import DockerManager
from fastapi_walletauth import JWTWalletAuthDep
from utils.models import HummingbotInstanceConfig, StartStrategyRequest, InstanceResponse
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

router = APIRouter(tags=["Bot Management"])
accounts_service = AccountsService()
docker_manager = DockerManager()
gateway_client = GatewayHttpClient.get_instance()


class CreateBotRequest(BaseModel):
    strategy_name: str
    strategy_parameters: dict
    market: str


@router.post("/bots", response_model=InstanceResponse)
async def create_bot(request: CreateBotRequest, wallet_auth: JWTWalletAuthDep):
    bot_account = f"robotter_{wallet_auth.address}_{request.market}_{request.strategy_name}"
    accounts_service.add_account(bot_account)
    wallet_address = await accounts_service.generate_bot_wallet(bot_account)

    # Save strategy configuration and market
    bot_config = BotConfig(
        strategy_name=request.strategy_name,
        parameters=request.strategy_parameters,
        market=request.market,
        wallet_address=wallet_auth.address,
    )
    accounts_service.save_bot_config(bot_account, bot_config)
    # Create Hummingbot instance
    instance_config = HummingbotInstanceConfig(
        instance_name=bot_account, credentials_profile=bot_account, image="mlguys/hummingbot:mango", market=request.market
    )
    result = docker_manager.create_hummingbot_instance(instance_config)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])

    return InstanceResponse(instance_id=bot_account, wallet_address=wallet_address, market=request.market)


@router.get("/bots/{bot_id}/wallet")
async def get_bot_wallet(bot_id: str, wallet_auth: JWTWalletAuthDep):
    try:
        # Check if the bot belongs to the authenticated user
        if not bot_id.endswith(wallet_auth.address):
            raise HTTPException(status_code=403, detail="You don't have permission to access this bot")

        wallet_address = accounts_service.get_bot_wallet_address(bot_id)
        return {"wallet_address": wallet_address}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/bots/{bot_id}/start")
async def start_bot(bot_id: str, start_request: StartStrategyRequest, wallet_auth: JWTWalletAuthDep):
    # Check if the bot belongs to the authenticated user
    bot_config = accounts_service.get_bot_config(bot_id)
    if not bot_config or bot_config.wallet_address != wallet_auth.address:
        raise HTTPException(status_code=403, detail="You don't have permission to start this bot")

    # Check if Mango account exists and is associated with the bot's wallet
    bot_wallet = accounts_service.get_bot_wallet_address(bot_id)

    # We should pass the wallet address
    mango_account_info = await gateway_client.get_mango_account(
        "solana", "mainnet", "mango_perpetual_solana_mainnet-beta", bot_wallet
    )

    if not mango_account_info or mango_account_info.get("owner") != bot_wallet:
        raise HTTPException(status_code=400, detail="Invalid Mango account or not associated with the bot's wallet")

    # Start the bot
    strategy_config = accounts_service.get_strategy_config(bot_id)
    start_config = {**strategy_config, **start_request.parameters}

    response = docker_manager.start_bot(bot_id, start_config)
    if not response["success"]:
        raise HTTPException(status_code=500, detail="Failed to start the bot")

    return {"status": "success", "message": "Bot started successfully"}


@router.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, wallet_auth: JWTWalletAuthDep):
    # Check if the bot belongs to the authenticated user
    if not bot_id.endswith(wallet_auth.address):
        raise HTTPException(status_code=403, detail="You don't have permission to stop this bot")

    # Stop the bot and cancel all orders
    response = docker_manager.stop_bot(bot_id)
    if not response["success"]:
        raise HTTPException(status_code=500, detail="Failed to stop the bot")

    # Cancel all orders through the gateway
    bot_wallet = accounts_service.get_bot_wallet_address(bot_id)
    cancel_orders_response = await gateway_client.clob_perp_get_orders("solana", "mainnet", "mango_perpetual_solana_mainnet-beta")

    if not cancel_orders_response["success"]:
        raise HTTPException(status_code=500, detail="Failed to cancel all orders")

    return {"status": "success", "message": "Bot stopped and all orders cancelled successfully"} 