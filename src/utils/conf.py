import os
from pathlib import Path
import hummingbot.client.settings as conf

def root_path():
    return Path("/backend-api")

def load_environment_variables():
    # Non-path variables
    conf.KEYFILE_PREFIX = os.environ.get("KEYFILE_PREFIX", conf.KEYFILE_PREFIX)
    conf.KEYFILE_POSTFIX = os.environ.get("KEYFILE_POSTFIX", conf.KEYFILE_POSTFIX)
    conf.ENCYPTED_CONF_POSTFIX = os.environ.get("ENCYPTED_CONF_POSTFIX", conf.ENCYPTED_CONF_POSTFIX)
    conf.DEFAULT_ETHEREUM_RPC_URL = os.environ.get("DEFAULT_ETHEREUM_RPC_URL", conf.DEFAULT_ETHEREUM_RPC_URL)
    conf.CONF_PREFIX = os.environ.get("CONF_PREFIX", conf.CONF_PREFIX)
    conf.CONF_POSTFIX = os.environ.get("CONF_POSTFIX", conf.CONF_POSTFIX)
    conf.SCRIPT_STRATEGIES_MODULE = os.environ.get("SCRIPT_STRATEGIES_MODULE", conf.SCRIPT_STRATEGIES_MODULE)
    conf.CONTROLLERS_MODULE = os.environ.get("CONTROLLERS_MODULE", conf.CONTROLLERS_MODULE)

    # Path variables
    conf.DEFAULT_LOG_FILE_PATH = Path(os.environ.get("DEFAULT_LOG_FILE_PATH", conf.DEFAULT_LOG_FILE_PATH or root_path() / "logs"))
    conf.TEMPLATE_PATH = Path(os.environ.get("TEMPLATE_PATH", conf.TEMPLATE_PATH or root_path() / "hummingbot" / "templates"))
    conf.CONF_DIR_PATH = Path(os.environ.get("CONF_DIR_PATH", conf.CONF_DIR_PATH or root_path() / "conf"))
    conf.CLIENT_CONFIG_PATH = Path(os.environ.get("CLIENT_CONFIG_PATH", conf.CLIENT_CONFIG_PATH or conf.CONF_DIR_PATH / "conf_client.yml"))
    conf.TRADE_FEES_CONFIG_PATH = Path(os.environ.get("TRADE_FEES_CONFIG_PATH", conf.TRADE_FEES_CONFIG_PATH or conf.CONF_DIR_PATH / "conf_fee_overrides.yml"))
    conf.STRATEGIES_CONF_DIR_PATH = Path(os.environ.get("STRATEGIES_CONF_DIR_PATH", conf.STRATEGIES_CONF_DIR_PATH or conf.CONF_DIR_PATH / "strategies"))
    conf.CONNECTORS_CONF_DIR_PATH = Path(os.environ.get("CONNECTORS_CONF_DIR_PATH", conf.CONNECTORS_CONF_DIR_PATH or conf.CONF_DIR_PATH / "connectors"))
    conf.SCRIPT_STRATEGY_CONF_DIR_PATH = Path(os.environ.get("SCRIPT_STRATEGY_CONF_DIR_PATH", conf.SCRIPT_STRATEGY_CONF_DIR_PATH or conf.CONF_DIR_PATH / "scripts"))
    conf.CONTROLLERS_CONF_DIR_PATH = Path(os.environ.get("CONTROLLERS_CONF_DIR_PATH", conf.CONTROLLERS_CONF_DIR_PATH or conf.CONF_DIR_PATH / "controllers"))
    conf.SCRIPT_STRATEGIES_PATH = Path(os.environ.get("SCRIPT_STRATEGIES_PATH", conf.SCRIPT_STRATEGIES_PATH or root_path() / conf.SCRIPT_STRATEGIES_MODULE))
    conf.CONTROLLERS_PATH = Path(os.environ.get("CONTROLLERS_PATH", conf.CONTROLLERS_PATH or root_path() / conf.CONTROLLERS_MODULE))
    conf.DEFAULT_GATEWAY_CERTS_PATH = Path(os.environ.get("DEFAULT_GATEWAY_CERTS_PATH", conf.DEFAULT_GATEWAY_CERTS_PATH or root_path() / "certs"))
    conf.GATEWAY_SSL_CONF_FILE = Path(os.environ.get("GATEWAY_SSL_CONF_FILE", conf.GATEWAY_SSL_CONF_FILE or root_path() / "gateway" / "conf" / "ssl.yml"))
    conf.GATEAWAY_CA_CERT_PATH = Path(os.environ.get("GATEAWAY_CA_CERT_PATH", conf.GATEAWAY_CA_CERT_PATH or conf.DEFAULT_GATEWAY_CERTS_PATH / "ca_cert.pem"))
    conf.GATEAWAY_CLIENT_CERT_PATH = Path(os.environ.get("GATEAWAY_CLIENT_CERT_PATH", conf.GATEAWAY_CLIENT_CERT_PATH or conf.DEFAULT_GATEWAY_CERTS_PATH / "client_cert.pem"))
    conf.GATEAWAY_CLIENT_KEY_PATH = Path(os.environ.get("GATEAWAY_CLIENT_KEY_PATH", conf.GATEAWAY_CLIENT_KEY_PATH or conf.DEFAULT_GATEWAY_CERTS_PATH / "client_key.pem"))
