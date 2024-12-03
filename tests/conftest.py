import pytest
from fastapi.testclient import TestClient
from contextlib import asynccontextmanager
import pytest_asyncio
from pathlib import Path
import os

# Set up paths before importing hummingbot
CONF_DIR = Path("/backend-api/conf")
os.environ["CONF_DIR_PATH"] = str(CONF_DIR)
os.environ["PASSWORD_VERIFICATION_PATH"] = str(CONF_DIR / ".password_verification")
os.environ["CLIENT_CONFIG_PATH"] = str(CONF_DIR / "conf_client.yml")
os.environ["HUMMINGBOT_CONF_DIR"] = str(CONF_DIR)

# Monkey patch hummingbot's config paths
import hummingbot.client.settings as settings
settings.CONF_DIR_PATH = CONF_DIR
settings.CLIENT_CONFIG_PATH = CONF_DIR / "conf_client.yml"
settings.PASSWORD_VERIFICATION_PATH = CONF_DIR / ".password_verification"
settings.GATEWAY_SSL_CONF_FILE = CONF_DIR / "ssl.yml"

# Create SSL config file
with open(settings.GATEWAY_SSL_CONF_FILE, "w") as f:
    f.write("cert_path: /backend-api/certs/server_cert.pem\n")
    f.write("key_path: /backend-api/certs/server_key.pem\n")
    f.write("passphrase: test_passphrase\n")

@asynccontextmanager
async def lifespan(app):
    """Async lifespan context manager for FastAPI app."""
    try:
        yield
    finally:
        # Cleanup any remaining connections or resources
        if hasattr(app.state, 'cleanup'):
            await app.state.cleanup()

@pytest_asyncio.fixture(scope="function")
async def test_app():
    """Create a test instance of the FastAPI application."""
    from main import app
    app.router.lifespan_context = lifespan
    async with lifespan(app):
        yield app

@pytest.fixture(scope="function")
def client(test_app):
    """Create a test client for the FastAPI application."""
    with TestClient(test_app) as client:
        yield client
        client.close()