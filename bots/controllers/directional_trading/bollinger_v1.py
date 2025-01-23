from typing import List

import pandas_ta as ta  # noqa: F401
from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from pydantic import Field, validator
import pandas as pd


class BollingerV1ControllerConfig(DirectionalTradingControllerConfigBase):
    controller_name = "bollinger_v1"
    candles_config: List[CandlesConfig] = []
    candles_connector: str = Field(default=None)
    candles_trading_pair: str = Field(default=None)
    interval: str = Field(
        default="3m",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            prompt_on_new=False))
    bb_length: int = Field(
        default=100,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands length: ",
            prompt_on_new=True))
    bb_std: float = Field(
        default=2.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands standard deviation: ",
            prompt_on_new=False))
    bb_long_threshold: float = Field(
        default=0.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands long threshold: ",
            prompt_on_new=True))
    bb_short_threshold: float = Field(
        default=1.0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the Bollinger Bands short threshold: ",
            prompt_on_new=True))

    @validator("candles_connector", pre=True, always=True)
    def set_candles_connector(cls, v, values):
        if v is None or v == "":
            return values.get("connector_name")
        return v

    @validator("candles_trading_pair", pre=True, always=True)
    def set_candles_trading_pair(cls, v, values):
        if v is None or v == "":
            return values.get("trading_pair")
        return v


class BollingerV1Controller(DirectionalTradingControllerBase):
    def __init__(self, config: BollingerV1ControllerConfig, *args, **kwargs):
        self.config = config
        self.max_records = self.config.bb_length
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        print("Starting update_processed_data in BollingerV1Controller")
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        print(f"Got candles DataFrame with shape: {df.shape}")
        print(f"DataFrame columns: {df.columns.tolist()}")
        
        # Add indicators using pandas_ta
        print(f"Calculating Bollinger Bands with length={self.config.bb_length}, std={self.config.bb_std}")
        bbands = df.ta.bbands(length=self.config.bb_length, std=self.config.bb_std)
        print(f"Bollinger Bands columns: {bbands.columns.tolist() if bbands is not None else 'None'}")
        
        df = pd.concat([df, bbands], axis=1)
        print(f"Combined DataFrame columns: {df.columns.tolist()}")

        # Generate signal
        bbp_col = f"BBP_{self.config.bb_length}_{self.config.bb_std}"
        print(f"Looking for BBP column: {bbp_col}")
        print(f"BBP values: {df[bbp_col].head() if bbp_col in df.columns else 'Column not found'}")
        
        long_condition = df[bbp_col] < self.config.bb_long_threshold
        short_condition = df[bbp_col] > self.config.bb_short_threshold

        # Generate signal
        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1
        print(f"Generated signals: {df['signal'].value_counts()}")

        # Update processed data
        self.processed_data["signal"] = df["signal"].iloc[-1]
        self.processed_data["features"] = df
        print("Finished update_processed_data")
