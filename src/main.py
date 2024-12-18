import sys
import os
from pathlib import Path

# Add project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from construct import ValidationError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse
from fastapi_walletauth import jwt_authorization_router as authorization_routes

from src.routers import bots, strategies, market_data, backtest, trades
from src.config.settings import get_settings

# Initialize settings
settings = get_settings()

# Configure logging
import logging
logger = logging.getLogger(__name__) if __name__ != "__main__" else logging.getLogger("uvicorn")
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))

app = FastAPI(
    title="Robotter Backend API",
    description="Trading bot management API",
    version="1.0.0",
    debug=settings.DEBUG
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/challenge")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with proper prefixes and tags
app.include_router(
    bots.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Bot Management"]
)
app.include_router(
    strategies.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Strategy Management"]
)
app.include_router(
    market_data.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Market Data"]
)
app.include_router(
    backtest.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Backtesting"]
)
app.include_router(
    trades.router,
    prefix=settings.API_V1_PREFIX,
    tags=["Bot Trading"]
)
app.include_router(authorization_routes)

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

@app.get("/")
def root():
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 