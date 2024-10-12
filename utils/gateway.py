import os
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.client.config.security import Security
from hummingbot.client.config.config_helpers import ClientConfigAdapter

from utils.conf import load_environment_variables

load_environment_variables()

class CustomGatewayHttpClient:
    def __init__(self, client_config_map: ClientConfigAdapter, secrets_manager):
        self.client_config_map = client_config_map
        self.secrets_manager = secrets_manager
        self.original_secrets_manager = Security.secrets_manager
        
        # Get gateway configuration from environment variables
        self.gateway_host = os.getenv("GATEWAY_HOST", "localhost")
        self.gateway_port = int(os.getenv("GATEWAY_PORT", "15888"))
        self.gateway_certs_path = os.getenv("GATEWAY_CERTS_PATH", "/certs")
        self.gateway_cert_path = os.path.join(self.gateway_certs_path, "gateway_cert.pem")

    def __enter__(self):
        Security.secrets_manager = self.secrets_manager
        self.client = GatewayHttpClient.get_instance(self.client_config_map)
        
        self.client.base_url = f"https://{self.gateway_host}:{self.gateway_port}"
        self.client.certs_path = self.gateway_certs_path
        self.client.cert_file = self.gateway_cert_path
        
        # Use SSL verification with the new certificate
        self.client.ssl = self.gateway_cert_path
        
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        Security.secrets_manager = self.original_secrets_manager

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)