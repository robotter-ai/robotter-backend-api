import asyncio
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import base58
from fastapi import HTTPException
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import ClientConfigAdapter, ReadOnlyClientConfigAdapter, get_connector_class, load_client_config_map_from_file
from hummingbot.client.settings import AllConnectorSettings

from config import BANNED_TOKENS, CONFIG_PASSWORD
from utils.file_system import FileSystemUtil
from utils.models import BackendAPIConfigAdapter
from utils.security import BackendAPISecurity

import os
from nacl.secret import SecretBox
from nacl.utils import random
from nacl.signing import SigningKey
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
import base64

file_system = FileSystemUtil()


class AccountsService:
    """
    This class is responsible for managing all the accounts that are connected to the trading system. It is responsible
    to initialize all the connectors that are connected to each account, keep track of the balances of each account and
    update the balances of each account.
    """

    def __init__(self,
                 update_account_state_interval_minutes: int = 1,
                 default_quote: str = "USDC",
                 account_history_file: str = "account_state_history.json",
                 account_history_dump_interval_minutes: int = 1):
        # TODO: Add database to store the balances of each account each time it is updated.
        self.secrets_manager = ETHKeyFileSecretManger(CONFIG_PASSWORD)
        self.accounts = {}
        self.accounts_state = {}
        self.account_state_update_event = asyncio.Event()
        self.initialize_accounts()
        self.update_account_state_interval = update_account_state_interval_minutes * 60
        self.default_quote = default_quote
        self.history_file = account_history_file
        self.account_history_dump_interval = account_history_dump_interval_minutes
        self._update_account_state_task: Optional[asyncio.Task] = None
        self._dump_account_state_task: Optional[asyncio.Task] = None
        # Load or generate a secret key for encryption
        self.secret_key = self._load_or_generate_secret_key()

    def _load_or_generate_secret_key(self):
        secret_key_path = "secret_key.txt"
        if os.path.exists(secret_key_path):
            with open(secret_key_path, "rb") as f:
                return f.read()
        else:
            secret_key = random(SecretBox.KEY_SIZE)
            with open(secret_key_path, "wb") as f:
                f.write(secret_key)
            return secret_key

    def get_accounts_state(self):
        return self.accounts_state

    def get_default_market(self, token):
        return f"{token}-{self.default_quote}"

    def start_update_account_state_loop(self):
        """
        Start the loop that updates the balances of all the accounts at a fixed interval.
        :return:
        """
        self._update_account_state_task = asyncio.create_task(self.update_account_state_loop())
        self._dump_account_state_task = asyncio.create_task(self.dump_account_state_loop())

    def stop_update_account_state_loop(self):
        """
        Stop the loop that updates the balances of all the accounts at a fixed interval.
        :return:
        """
        if self._update_account_state_task:
            self._update_account_state_task.cancel()
        if self._dump_account_state_task:
            self._dump_account_state_task.cancel()
        self._update_account_state_task = None
        self._dump_account_state_task = None

    async def update_account_state_loop(self):
        """
        The loop that updates the balances of all the accounts at a fixed interval.
        :return:
        """
        while True:
            try:
                await self.check_all_connectors()
                await self.update_balances()
                await self.update_trading_rules()
                await self.update_account_state()
            except Exception as e:
                logging.error(f"Error updating account state: {e}")
            finally:
                await asyncio.sleep(self.update_account_state_interval)

    async def dump_account_state_loop(self):
        """
        The loop that dumps the current account state to a file at fixed intervals.
        :return:
        """
        await self.account_state_update_event.wait()
        while True:
            try:
                await self.dump_account_state()
            except Exception as e:
                logging.error(f"Error dumping account state: {e}")
            finally:
                now = datetime.now()
                next_log_time = (now + timedelta(minutes=self.account_history_dump_interval)).replace(second=0,
                                                                                                      microsecond=0)
                next_log_time = next_log_time - timedelta(
                    minutes=next_log_time.minute % self.account_history_dump_interval)
                sleep_duration = (next_log_time - now).total_seconds()
                await asyncio.sleep(sleep_duration)

    async def dump_account_state(self):
        """
        Dump the current account state to a JSON file. Create it if the file not exists.
        :return:
        """
        timestamp = datetime.now().isoformat()
        state_to_dump = {"timestamp": timestamp, "state": self.accounts_state}
        if not file_system.path_exists(path=f"data/{self.history_file}"):
            file_system.add_file(directory="data", file_name=self.history_file, content=json.dumps(state_to_dump) + "\n")
        else:
            file_system.append_to_file(directory="data", file_name=self.history_file, content=json.dumps(state_to_dump) + "\n")

    def load_account_state_history(self):
        """
        Load the account state history from the JSON file.
        :return: List of account states with timestamps.
        """
        history = []
        try:
            with open("bots/data/" + self.history_file, "r") as file:
                for line in file:
                    if line.strip():  # Check if the line is not empty
                        history.append(json.loads(line))
        except FileNotFoundError:
            logging.warning("No account state history file found.")
        return history

    async def check_all_connectors(self):
        """
        Check all avaialble credentials for all accounts and see if the connectors are created.
        :return:
        """
        for account_name in self.list_accounts():
            for connector_name in self.list_credentials(account_name):
                try:
                    connector_name = connector_name.split(".")[0]
                    if account_name not in self.accounts or connector_name not in self.accounts[account_name]:
                        self.initialize_connector(account_name, connector_name)
                except Exception as e:
                    logging.error(f"Error initializing connector {connector_name}: {e}")

    def initialize_accounts(self):
        """
        Initialize all the connectors that are connected to each account.
        :return:
        """
        for account_name in self.list_accounts():
            self.accounts[account_name] = {}
            for connector_name in self.list_credentials(account_name):
                try:
                    connector_name = connector_name.split(".")[0]
                    connector = self.get_connector(account_name, connector_name)
                    self.accounts[account_name][connector_name] = connector
                except Exception as e:
                    logging.error(f"Error initializing connector {connector_name}: {e}")

    def initialize_account(self, account_name: str):
        """
        Initialize all the connectors that are connected to the specified account.
        :param account_name: The name of the account.
        :return:
        """
        for connector_name in self.list_credentials(account_name):
            try:
                connector_name = connector_name.split(".")[0]
                self.initialize_connector(account_name, connector_name)
            except Exception as e:
                logging.error(f"Error initializing connector {connector_name}: {e}")

    def initialize_connector(self, account_name: str, connector_name: str):
        """
        Initialize the specified connector for the specified account.
        :param account_name: The name of the account.
        :param connector_name: The name of the connector.
        :return:
        """
        if account_name not in self.accounts:
            self.accounts[account_name] = {}
        try:
            connector = self.get_connector(account_name, connector_name)
            self.accounts[account_name][connector_name] = connector
        except Exception as e:
            logging.error(f"Error initializing connector {connector_name}: {e}")

    async def update_balances(self):
        tasks = []
        for account_name, connectors in self.accounts.items():
            for connector_instance in connectors.values():
                tasks.append(self._safe_update_balances(connector_instance))
        await asyncio.gather(*tasks)

    async def _safe_update_balances(self, connector_instance):
        try:
            await connector_instance._update_balances()
        except Exception as e:
            logging.error(f"Error updating balances for connector {connector_instance}: {e}")

    async def update_trading_rules(self):
        tasks = []
        for account_name, connectors in self.accounts.items():
            for connector_instance in connectors.values():
                tasks.append(self._safe_update_trading_rules(connector_instance))
        await asyncio.gather(*tasks)

    async def _safe_update_trading_rules(self, connector_instance):
        try:
            await connector_instance._update_trading_rules()
        except Exception as e:
            logging.error(f"Error updating trading rules for connector {connector_instance}: {e}")

    async def update_account_state(self):
        for account_name, connectors in self.accounts.items():
            if account_name not in self.accounts_state:
                self.accounts_state[account_name] = {}
            for connector_name, connector in connectors.items():
                tokens_info = []
                try:
                    balances = [{"token": key, "units": value} for key, value in connector.get_all_balances().items() if
                                value != Decimal("0") and key not in BANNED_TOKENS]
                    unique_tokens = [balance["token"] for balance in balances]
                    trading_pairs = [self.get_default_market(token) for token in unique_tokens if "USD" not in token]
                    last_traded_prices = await self._safe_get_last_traded_prices(connector, trading_pairs)
                    for balance in balances:
                        token = balance["token"]
                        if "USD" in token:
                            price = Decimal("1")
                        else:
                            market = self.get_default_market(balance["token"])
                            price = Decimal(last_traded_prices.get(market, 0))
                        tokens_info.append({
                            "token": balance["token"],
                            "units": float(balance["units"]),
                            "price": float(price),
                            "value": float(price * balance["units"]),
                            "available_units": float(connector.get_available_balance(balance["token"]))
                        })
                    self.account_state_update_event.set()
                except Exception as e:
                    logging.error(
                        f"Error updating balances for connector {connector_name} in account {account_name}: {e}")
                self.accounts_state[account_name][connector_name] = tokens_info

    async def _safe_get_last_traded_prices(self, connector, trading_pairs, timeout=5):
        try:
            # TODO: Fix OKX connector to return the markets in Hummingbot format.
            last_traded = await asyncio.wait_for(connector.get_last_traded_prices(trading_pairs=trading_pairs), timeout=timeout)
            if connector.name == "okx_perpetual":
                return {pair.strip("-SWAP"): value for pair, value in last_traded.items()}
            return last_traded
        except asyncio.TimeoutError:
            logging.error(f"Timeout getting last traded prices for trading pairs {trading_pairs}")
            return {pair: Decimal("0") for pair in trading_pairs}
        except Exception as e:
            logging.error(f"Error getting last traded prices for trading pairs {trading_pairs}: {e}")
            return {pair: Decimal("0") for pair in trading_pairs}

    @staticmethod
    def get_connector_config_map(connector_name: str):
        """
        Get the connector config map for the specified connector.
        :param connector_name: The name of the connector.
        :return: The connector config map.
        """
        connector_config = BackendAPIConfigAdapter(AllConnectorSettings.get_connector_config_keys(connector_name))
        return [key for key in connector_config.hb_config.__fields__.keys() if key != "connector"]

    async def add_connector_keys(self, account_name: str, connector_name: str, keys: dict):
        BackendAPISecurity.login_account(account_name=account_name, secrets_manager=self.secrets_manager)
        connector_config = BackendAPIConfigAdapter(AllConnectorSettings.get_connector_config_keys(connector_name))
        for key, value in keys.items():
            setattr(connector_config, key, value)
        BackendAPISecurity.update_connector_keys(account_name, connector_config)
        new_connector = self.get_connector(account_name, connector_name)
        await new_connector._update_balances()
        self.accounts[account_name][connector_name] = new_connector
        await self.update_account_state()
        await self.dump_account_state()

    def get_connector(self, account_name: str, connector_name: str):
        """
        Get the connector object for the specified account and connector.
        :param account_name: The name of the account.
        :param connector_name: The name of the connector.
        :return: The connector object.
        """
        BackendAPISecurity.login_account(account_name=account_name, secrets_manager=self.secrets_manager)
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        conn_setting = AllConnectorSettings.get_connector_settings()[connector_name]
        keys = BackendAPISecurity.api_keys(connector_name)
        read_only_config = ReadOnlyClientConfigAdapter.lock_config(client_config_map)
        init_params = conn_setting.conn_init_parameters(
            trading_pairs=[],
            trading_required=True,
            api_keys=keys,
            client_config_map=read_only_config,
        )
        connector_class = get_connector_class(connector_name)
        connector = connector_class(**init_params)
        return connector
    
    @staticmethod
    def list_accounts():
        """
        List all the accounts that are connected to the trading system.
        :return: List of accounts.
        """
        if not file_system.path_exists('credentials'):
            return []
        return file_system.list_folders('credentials')

    def list_credentials(self, account_name: str):
        """
        List all the credentials that are connected to the specified account.
        :param account_name: The name of the account.
        :return: List of credentials.
        """
        try:
            return [file for file in file_system.list_files(f'credentials/{account_name}/connectors') if
                    file.endswith('.yml')]
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    def delete_credentials(self, account_name: str, connector_name: str):
        """
        Delete the credentials of the specified connector for the specified account.
        :param account_name:
        :param connector_name:
        :return:
        """
        if file_system.path_exists(f"credentials/{account_name}/connectors/{connector_name}.yml"):
            file_system.delete_file(directory=f"credentials/{account_name}/connectors", file_name=f"{connector_name}.yml")
            if connector_name in self.accounts[account_name]:
                self.accounts[account_name].pop(connector_name)
            if connector_name in self.accounts_state[account_name]:
                self.accounts_state[account_name].pop(connector_name)

    def add_account(self, account_name: str):
        """
        Add a new account.
        :param account_name:
        :return:
        """
        if account_name in self.accounts:
            raise HTTPException(status_code=400, detail="Account already exists.")
        files_to_copy = ["conf_client.yml", "conf_fee_overrides.yml", "hummingbot_logs.yml", ".password_verification"]
        file_system.create_folder('credentials', account_name)
        file_system.create_folder(f'credentials/{account_name}', "connectors")
        for file in files_to_copy:
            file_system.copy_file(f"credentials/master_account/{file}", f"credentials/{account_name}/{file}")
        self.accounts[account_name] = {"wallet": None}
        self.accounts_state[account_name] = {}

    def delete_account(self, account_name: str):
        """
        Delete the specified account.
        :param account_name:
        :return:
        """
        file_system.delete_folder('credentials', account_name)
        self.accounts.pop(account_name)
        self.accounts_state.pop(account_name)

    async def generate_bot_wallet(self, account_name: str) -> str:
        signing_key = SigningKey.generate()
        wallet_address = base58.b58encode(signing_key.verify_key.encode()).decode()
        private_key = signing_key.encode().hex()
        self._save_private_key(account_name, wallet_address, private_key)
        # await self._add_wallet_to_gateway(account_name, wallet_address, private_key)
        self._add_wallet_to_account(account_name, wallet_address)
        return wallet_address

    def _save_private_key(self, account_name: str, wallet_address: str, private_key: str):
        # Encrypt the private key
        encrypted_private_key = self._encrypt_private_key(private_key)
        
        # Prepare the file path
        credentials_dir = os.path.join("bots", "credentials", account_name)
        os.makedirs(credentials_dir, exist_ok=True)
        wallet_path = os.path.join(credentials_dir, "solana")
        os.makedirs(wallet_path, exist_ok=True)
        key_file_path = os.path.join(wallet_path, f"{wallet_address}.json")
        
        # Save the encrypted private key
        with open(key_file_path, "w") as f:
            json.dump(encrypted_private_key, f)
        
        # Set restrictive permissions on the file
        os.chmod(key_file_path, 0o600)

    def _encrypt_private_key(self, private_key: str) -> str:
        box = SecretBox(self.secret_key)
        encrypted = box.encrypt(private_key.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt_private_key(self, encrypted_private_key: str) -> str:
        box = SecretBox(self.secret_key)
        decrypted = box.decrypt(base64.b64decode(encrypted_private_key))
        return decrypted.decode()
    
    def get_gateway_client(self, account_name: str):
        config_map = load_client_config_map_from_file('/backend-api/conf/conf_client.yml')
        BackendAPISecurity.login_account(account_name=account_name, secrets_manager=self.secrets_manager)
        client_config_adapter = ClientConfigAdapter(config_map)

        return GatewayHttpClient.get_instance(client_config_adapter)

    async def _add_wallet_to_gateway(self, account_name: str, wallet_address: str, private_key: str):
        # TODO: FIX the /backend/api/certs/ca_cert.pem path
        gateway_client = self.get_gateway_client(account_name)
        
        # Assuming there's a method to add a Solana wallet to the gateway
        # You may need to adjust this based on the actual Gateway API
        response = await gateway_client.add_wallet(
            chain="solana",
            network="mainnet",
            private_key=private_key,
            address=wallet_address
        )
        
        if not response["success"]:
            raise Exception(f"Failed to add wallet to gateway: {response['message']}")
    
    def _add_wallet_to_account(self, account_name: str, wallet_address: str):
        if account_name not in self.accounts:
            raise ValueError(f"Account {account_name} does not exist.")
        self.accounts[account_name]["wallet"] = wallet_address
        self._save_account_info(account_name)

    def _save_account_info(self, account_name: str):
        account_info_path = f"bots/credentials/{account_name}/account_info.json"
        with open(account_info_path, "w") as f:
            json.dump(self.accounts[account_name], f)

    def get_bot_wallet_address(self, account_name: str) -> str:
        if account_name not in self.accounts or not self.accounts[account_name]["wallet"]:
            account_info_path = f"bots/credentials/{account_name}/account_info.json"
            try:
                with open(account_info_path, "r") as f:
                    account_info = json.load(f)
                    self.accounts[account_name] = account_info
            except FileNotFoundError:
                raise ValueError(f"No wallet found for bot account: {account_name}")
        
        return self.accounts[account_name]["wallet"]

    def get_bot_wallet_private_key(self, credentials_profile: str, wallet_address: str) -> str:
        wallet_path = os.path.join("bots", "credentials", credentials_profile, "solana")
        key_file_path = os.path.join(wallet_path, f"{wallet_address}.json")
        
        with open(key_file_path, "r") as f:
            encrypted_private_key = json.load(f)
        
        return self._decrypt_private_key(encrypted_private_key)

    def save_bot_config(self, account_name: str, strategy_name: str, parameters: dict, market: str):
        config_path = f"bots/credentials/{account_name}/bot_config.json"
        config = {
            "strategy_name": strategy_name,
            "parameters": parameters,
            "market": market
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

    def get_bot_config(self, account_name: str):
        config_path = f"bots/credentials/{account_name}/bot_config.json"
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"No configuration found for bot account: {account_name}")

    def get_bot_market(self, account_name: str):
        config = self.get_bot_config(account_name)
        return config["market"]