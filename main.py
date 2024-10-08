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

import routers.instances
import routers.strategies
import routers.market_data
import routers.backtest
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


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

app.include_router(routers.instances.router)
app.include_router(routers.strategies.router)
app.include_router(routers.market_data.router)
app.include_router(routers.backtest.router)
app.include_router(authorization_routes)

@app.get("/")
def root():
    return RedirectResponse(url="/docs")