from typing import List

from fastapi import APIRouter
from .strategy_models import StrategyParameter, convert_config_to_strategy_format

router = APIRouter(tags=["Instance Management"])


@router.get("/strategies", response_model=List[StrategyParameter])
async def get_strategies():
    strategies = []

    # Add pure market making strategy
    pure_market_making = convert_config_to_strategy_format(pure_market_making_config_map)
    strategies.append(pure_market_making)

    return strategies
