from decimal import Decimal
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi_walletauth import JWTWalletAuthDep, jwt_authorization_router
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map

from config import BROKER_HOST, BROKER_PASSWORD, BROKER_PORT, BROKER_USERNAME
from services.bots_orchestrator import BotsManager
from services.docker_service import DockerManager
from utils.models import HummingbotInstanceConfig, Instance, InstanceStats, StartStrategyRequest, InstanceResponse
from .strategy_models import Strategy, convert_config_to_strategy_format

router = APIRouter(tags=["Instance Management"])
router.include_router(jwt_authorization_router)

docker_manager = DockerManager()
bots_manager = BotsManager(broker_host=BROKER_HOST, broker_port=BROKER_PORT, 
                           broker_username=BROKER_USERNAME, broker_password=BROKER_PASSWORD)


@router.post("/instance", response_model=InstanceResponse)
async def create_instance(wallet_auth: JWTWalletAuthDep):
    # Create a new Hummingbot instance
    instance_config = HummingbotInstanceConfig(
        instance_name=f"instance_{wallet_auth.address}",
        credentials_profile="master_account",
        image="hummingbot/hummingbot:latest"
    )
    #result = docker_manager.create_hummingbot_instance(instance_config)
    #if result["success"]:
    if True:
        # Generate a wallet address for the instance (this is a placeholder, implement actual wallet generation)
        wallet_address = wallet_auth.address
        return InstanceResponse(instance_id=instance_config.instance_name, wallet_address=wallet_address)
    else:
        raise HTTPException(status_code=500, detail=result["message"])

@router.delete("/instance/{instance_id}")
async def delete_instance(instance_id: str, wallet_auth: JWTWalletAuthDep):
    #response = docker_manager.delete_hummingbot_instance(instance_id)
    #if not response["success"]:
    #    raise HTTPException(status_code=500, detail=response["message"])
    return {"status": "success", "message": "Instance deleted successfully"}

@router.get("/instances", response_model=List[Instance])
async def get_instances():
    active_containers = docker_manager.get_active_containers()
    instances = []
    for container_name in active_containers:
        status = bots_manager.get_bot_status(container_name)
        instances.append(Instance(
            id=container_name,
            wallet_address="0x1234567890123456789012345678901234567890",  # Placeholder
            running_status=status["status"] == "running",
            deployed_strategy=status["performance"].get("strategy", None) if status["status"] == "running" else None
        ))
    return instances

@router.get("/instance/{instance_id}/stats", response_model=InstanceStats)
async def get_instance_stats(instance_id: str, wallet_auth: JWTWalletAuthDep):
    status = bots_manager.get_bot_status(instance_id)
    if status["status"] == "error":
        raise HTTPException(status_code=404, detail="Instance not found")
    # Extract PNL from the performance data (this is a placeholder, implement actual PNL calculation)
    pnl = Decimal("0.0")
    for controller in status["performance"].values():
        if "performance" in controller and "pnl" in controller["performance"]:
            pnl += Decimal(str(controller["performance"]["pnl"]))
    return InstanceStats(pnl=pnl)

@router.get("/strategies", response_model=List[Strategy])
async def get_strategies():
    strategies = []

    # Add pure market making strategy
    pure_market_making = convert_config_to_strategy_format(pure_market_making_config_map)
    strategies.append(pure_market_making)

    return strategies

#@router.post("/instance", response_model=StartStrategyRequest)
#async def create_instance(wallet_auth: JWTWalletAuthDep):
#    #TODO: Return wallet address of bot
#    return StartStrategyRequest(strategy_name="simple_market_making", parameters={"bid_spread": "float", "ask_spread": "float"})

@router.put("/instance/{instance_id}/start")
async def start_instance(instance_id: str, start_request: StartStrategyRequest, wallet_auth: JWTWalletAuthDep):
    response = bots_manager.start_bot(instance_id, script=start_request.strategy_name, conf=start_request.parameters)
    if not response:
        raise HTTPException(status_code=500, detail="Failed to start the instance")
    return {"status": "success", "message": "Instance started successfully"}

@router.post("/strategies/{instance_id}/stop")
async def stop_instance(instance_id: str, wallet_auth: JWTWalletAuthDep):
    response = bots_manager.stop_bot(instance_id)
    if not response:
        raise HTTPException(status_code=500, detail="Failed to stop the instance")
    return {"status": "success", "message": "Instance stopped successfully"}
