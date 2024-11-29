import sys
import os

from construct import ValidationError
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from utils.conf import load_environment_variables

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hummingbot.client.settings  # load once to set hummingbot config
load_dotenv()
load_environment_variables()

import logging

logger = (
    logging.getLogger(__name__)
    if __name__ != "__main__"
    else logging.getLogger("uvicorn")
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import os
from fastapi_walletauth import jwt_authorization_router as authorization_routes
from starlette.responses import RedirectResponse

import routers.bots
import routers.strategies
import routers.market_data
import routers.backtest
import routers.trades

app = FastAPI()

os.environ['FASTAPI_WALLETAUTH_APP'] = 'robotter-ai'

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/challenge")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - only include each router once with proper prefix and tags
app.include_router(routers.bots.router, prefix="/api/v1", tags=["Bot Management"])
app.include_router(routers.strategies.router, prefix="/api/v1", tags=["Strategy Management"])
app.include_router(routers.market_data.router, prefix="/api/v1", tags=["Market Data"])
app.include_router(routers.backtest.router, prefix="/api/v1", tags=["Backtesting"])
app.include_router(routers.trades.router, prefix="/api/v1", tags=["Bot Trading"])
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