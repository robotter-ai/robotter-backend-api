from typing import Dict

from fastapi import APIRouter
from .strategies_models import StrategyParameter, get_all_strategy_maps

router = APIRouter(tags=["Strategies"])


@router.get("/strategies", response_model=Dict[str, Dict[str, StrategyParameter]])
async def get_strategies():
    return get_all_strategy_maps()
