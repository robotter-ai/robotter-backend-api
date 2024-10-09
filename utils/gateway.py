from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.client.config.security import Security
from hummingbot.client.config.config_helpers import ClientConfigAdapter

class CustomGatewayHttpClient:
    def __init__(self, client_config_map: ClientConfigAdapter, secrets_manager):
        self.client_config_map = client_config_map
        self.secrets_manager = secrets_manager
        self.original_secrets_manager = Security.secrets_manager

    def __enter__(self):
        Security.secrets_manager = self.secrets_manager
        self.client = GatewayHttpClient.get_instance(self.client_config_map)
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        Security.secrets_manager = self.original_secrets_manager

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)