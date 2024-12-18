from fastapi import APIRouter, HTTPException
from typing import List

from services.bots_orchestrator import BotsManager
from .trade_models import TradeHistoryResponse, PerformanceResponse

router = APIRouter(tags=["Bot Trading"])

@router.get("/bots/{bot_id}/trades", response_model=TradeHistoryResponse)
async def get_bot_trades(bot_id: str) -> TradeHistoryResponse:
    """
    Get the trade history for a specific bot
    """
    try:
        bots_manager = BotsManager.get_instance()
        if bot_id not in bots_manager.active_bots:
            raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
        # Get trade history from the bot
        trade_history = bots_manager.get_bot_history(bot_id)
        
        return TradeHistoryResponse(
            bot_name=bot_id,
            trades=trade_history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bots/{bot_id}/performance", response_model=PerformanceResponse)
async def get_bot_performance(bot_id: str) -> PerformanceResponse:
    """
    Get performance statistics for a specific bot
    """
    try:
        bots_manager = BotsManager.get_instance()
        if bot_id not in bots_manager.active_bots:
            raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
        # Get bot status which includes performance metrics
        bot_status = bots_manager.get_bot_status(bot_id)
        
        # Extract performance data from controllers
        controllers_performance = bot_status.get("performance", {})
        cleaned_performance = bots_manager.determine_controller_performance(controllers_performance)
        
        # Aggregate performance across all controllers
        total_pnl = sum(float(p["performance"].get("total_pnl", 0)) 
                       for p in cleaned_performance.values() 
                       if p["status"] == "running")
        
        total_trades = sum(int(p["performance"].get("total_trades", 0)) 
                          for p in cleaned_performance.values() 
                          if p["status"] == "running")
        
        # Calculate aggregated statistics
        stats = {
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "win_rate": sum(float(p["performance"].get("win_rate", 0)) 
                           for p in cleaned_performance.values() 
                           if p["status"] == "running") / len(cleaned_performance) if cleaned_performance else 0,
            "profit_loss_ratio": sum(float(p["performance"].get("profit_loss_ratio", 0)) 
                                   for p in cleaned_performance.values() 
                                   if p["status"] == "running") / len(cleaned_performance) if cleaned_performance else 0,
            "max_drawdown": max((float(p["performance"].get("max_drawdown", 0)) 
                               for p in cleaned_performance.values() 
                               if p["status"] == "running"), default=0),
            "start_timestamp": min((int(p["performance"].get("start_timestamp", 0)) 
                                  for p in cleaned_performance.values() 
                                  if p["status"] == "running"), default=0),
            "end_timestamp": max((int(p["performance"].get("end_timestamp", 0)) 
                                for p in cleaned_performance.values() 
                                if p["status"] == "running"), default=0),
            "active_positions": [p["performance"].get("active_positions", []) 
                               for p in cleaned_performance.values() 
                               if p["status"] == "running"],
            "performance_by_trading_pair": {
                controller_id: perf["performance"]
                for controller_id, perf in cleaned_performance.items()
                if perf["status"] == "running"
            }
        }
        
        return PerformanceResponse(
            bot_name=bot_id,
            stats=stats
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 