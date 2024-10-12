import asyncio
import time
import os
import datetime
from enum import Enum
from typing import List

import aiohttp
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from matplotlib import gridspec
from matplotlib.pylab import date2num
from dotenv import load_dotenv
from pydantic import BaseModel

# Enum classes
class CandleInterval(Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"

class CandleConnector(Enum):
    BIRDEYE = "birdeye"
    BINANCE = "binance"

# Data models
class HistoricalCandlesConfig(BaseModel):
    connector_name: CandleConnector = CandleConnector.BIRDEYE
    trading_pair: str = "SOL-PERP"
    market_address: str = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"  # Mango SOL-PERP
    interval: CandleInterval = CandleInterval.FIFTEEN_MINUTES
    start_time: int = int(time.time()) - 60 * 60 * 24 * 7  # 1 week ago
    end_time: int = int(time.time())

class CandleData(BaseModel):
    o: float  # Open
    h: float  # High
    l: float  # Low
    c: float  # Close
    v: float  # Volume
    unixTime: int
    address: str
    type: str

class HistoricalCandlesResponse(BaseModel):
    data: List[CandleData]

# Fetching data
async def fetch_birdeye_data(config: HistoricalCandlesConfig) -> HistoricalCandlesResponse:
    load_dotenv()
    birdeye_api_key = os.getenv("BIRDEYE_API_KEY")
    if not birdeye_api_key:
        raise ValueError("BIRDEYE_API_KEY not found in environment variables")

    url = f"https://public-api.birdeye.so/defi/ohlcv?address={config.market_address}&type={config.interval.value}&time_from={config.start_time}&time_to={config.end_time}"
    headers = {
        "accept": "application/json",
        "X-API-KEY": birdeye_api_key
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                candle_data = [CandleData(**item) for item in data['data']['items']]
                return HistoricalCandlesResponse(data=candle_data)
            else:
                raise Exception(f"Failed to fetch data: {response.status}")

# Volume Profile Calculation
def calculate_volume_profile(
    candles: List[CandleData],
    bin_size: float = 0.1,
    discount_old_candles: bool = False
) -> (np.ndarray, np.ndarray):
    # Determine min and max prices
    min_price = min(candle.l for candle in candles)
    max_price = max(candle.h for candle in candles)

    # Define price bins
    bins = np.arange(min_price, max_price + bin_size, bin_size)

    # Initialize volume per bin
    volume_profile = np.zeros(len(bins) - 1)

    # Optionally calculate weights to discount older candles
    if discount_old_candles:
        # Calculate weights using logarithmic decay
        time_deltas = np.array([candle.unixTime for candle in candles])
        current_time = max(time_deltas)
        time_deltas = current_time - time_deltas
        weights = np.log1p(time_deltas)  # Natural log of (1 + delta)
        weights = weights / np.max(weights)  # Normalize to [0,1]
        weights = 1 - weights  # Invert so newer candles have higher weight
    else:
        weights = np.ones(len(candles))

    # Distribute volume across bins
    for idx, candle in enumerate(candles):
        low = candle.l
        high = candle.h
        volume = candle.v * weights[idx]

        # Find bins that the candle spans
        start_idx = np.searchsorted(bins, low, side='right') - 1
        end_idx = np.searchsorted(bins, high, side='left')

        if start_idx >= end_idx:
            continue  # Skip if the candle doesn't span any bins

        num_bins = end_idx - start_idx
        volume_per_bin = volume / num_bins

        volume_profile[start_idx:end_idx] += volume_per_bin

    bin_centers = bins[:-1] + bin_size / 2
    return bin_centers, volume_profile

# Shadow Index Calculations
def calculate_all_shadow_indices(
    candles: List[CandleData],
    window_size: int = 14
) -> (dict, List[datetime.datetime], List[float], List[CandleData]):
    # Ensure there are enough candles
    if len(candles) < window_size:
        raise ValueError("Not enough candles to calculate shadow indices with the given window size.")

    # Calculate upper and lower shadows
    upper_shadows = np.array([candle.h - max(candle.o, candle.c) for candle in candles])
    lower_shadows = np.array([min(candle.o, candle.c) - candle.l for candle in candles])
    total_shadows = upper_shadows + lower_shadows

    # Original Shadow Index (Total Shadows)
    shadow_index = total_shadows

    # Detrended Shadow Index using SMA
    moving_avg_sma = np.convolve(total_shadows, np.ones(window_size)/window_size, mode='valid')
    detrended_shadow_index_sma = total_shadows[window_size - 1:] - moving_avg_sma

    # Detrended Shadow Index using EMA
    ema_alpha = 2 / (window_size + 1)
    moving_avg_ema = np.zeros_like(total_shadows)
    moving_avg_ema[0] = total_shadows[0]  # Initialize EMA with the first value

    for i in range(1, len(total_shadows)):
        moving_avg_ema[i] = ema_alpha * total_shadows[i] + (1 - ema_alpha) * moving_avg_ema[i - 1]

    detrended_shadow_index_ema = total_shadows - moving_avg_ema

    # Adjust arrays for alignment
    adjusted_shadow_index = shadow_index[window_size - 1:]
    adjusted_detrended_sma = detrended_shadow_index_sma
    adjusted_detrended_ema = detrended_shadow_index_ema[window_size - 1:]

    # Calculate Modified Shadow Index
    # Price Range Calculation
    price_ranges = np.array([candle.h - candle.l for candle in candles])
    # Avoid division by zero by adding a small epsilon
    epsilon = 1e-6
    price_ranges = np.where(price_ranges == 0, epsilon, price_ranges)
    # Average Price Range over the window
    avg_price_ranges = np.convolve(price_ranges, np.ones(window_size)/window_size, mode='valid')
    adjusted_price_ranges = price_ranges[window_size - 1:]
    # Volumes
    volumes = np.array([candle.v for candle in candles])[window_size - 1:]
    # Modified Shadow Index
    modified_shadow_index = volumes * (avg_price_ranges / adjusted_price_ranges)

    # Dates and Candles aligned
    adjusted_candles = candles[window_size - 1:]
    dates = [datetime.datetime.fromtimestamp(candle.unixTime) for candle in adjusted_candles]
    dates_numeric = [date2num(date) for date in dates]

    # Ensure all arrays have the same length
    lengths = [
        len(adjusted_shadow_index),
        len(adjusted_detrended_sma),
        len(adjusted_detrended_ema),
        len(modified_shadow_index),
        len(dates),
        len(adjusted_candles)
    ]
    min_len = min(lengths)
    adjusted_shadow_index = adjusted_shadow_index[:min_len]
    adjusted_detrended_sma = adjusted_detrended_sma[:min_len]
    adjusted_detrended_ema = adjusted_detrended_ema[:min_len]
    modified_shadow_index = modified_shadow_index[:min_len]
    dates = dates[:min_len]
    dates_numeric = dates_numeric[:min_len]
    adjusted_candles = adjusted_candles[:min_len]

    # Combine indices into a dictionary
    indices = {
        'shadow_index': adjusted_shadow_index,
        'detrended_shadow_index_sma': adjusted_detrended_sma,
        'detrended_shadow_index_ema': adjusted_detrended_ema,
        'modified_shadow_index': modified_shadow_index
    }

    return indices, dates, dates_numeric, adjusted_candles

# Plotting Functions
def plot_volume_profile(bin_centers: np.ndarray, volume_profile: np.ndarray):
    plt.figure(figsize=(10, 8))
    plt.barh(bin_centers, volume_profile, height=bin_centers[1] - bin_centers[0], color='blue', edgecolor='black')
    plt.xlabel('Volume')
    plt.ylabel('Price')
    plt.title('Volume Profile')
    plt.gca().invert_yaxis()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_candles_and_all_shadow_indices(
    dates: List[datetime.datetime],
    dates_numeric: List[float],
    candles: List[CandleData],
    indices: dict
):
    fig = plt.figure(figsize=(14, 12))
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 2])

    # Subplot 1: Candlestick chart
    ax0 = plt.subplot(gs[0])
    plt.title('Candlestick Chart')

    # Prepare candlestick data
    candlestick_data = []
    for idx, candle in enumerate(candles):
        open_price = candle.o
        high_price = candle.h
        low_price = candle.l
        close_price = candle.c
        date_num = dates_numeric[idx]
        candlestick_data.append((date_num, open_price, high_price, low_price, close_price))

    # Plot candlesticks
    try:
        from mplfinance.original_flavor import candlestick_ohlc
    except ImportError:
        from mpl_finance import candlestick_ohlc  # Or handle import accordingly

    candlestick_ohlc(ax0, candlestick_data, width=0.0008, colorup='g', colordown='r', alpha=0.8)

    ax0.xaxis_date()
    ax0.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.setp(ax0.get_xticklabels(), rotation=45)
    ax0.grid(True)

    # Subplot 2: Shadow indices
    ax1 = plt.subplot(gs[1], sharex=ax0)
    plt.title('Shadow Indices')
    ax1.plot(dates_numeric, indices['shadow_index'], label='Shadow Index', color='blue', linewidth=0.5)
    ax1.plot(dates_numeric, indices['detrended_shadow_index_sma'], label='Detrended SI (SMA)', color='purple', linewidth=0.5)
    ax1.plot(dates_numeric, indices['detrended_shadow_index_ema'], label='Detrended SI (EMA)', color='green', linewidth=0.5)
    ax1.plot(dates_numeric, indices['modified_shadow_index'], label='Modified SI', color='red', linewidth=0.5)
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Shadow Index')
    ax1.legend()
    ax1.grid(True)

    plt.tight_layout()
    plt.show()

# Main Function
async def main():
    # Fetch historical candle data
    config = HistoricalCandlesConfig()
    candles_response = await fetch_birdeye_data(config)
    candles = candles_response.data

    # Sort candles by unixTime to ensure correct order
    candles = sorted(candles, key=lambda x: x.unixTime)

    # Ensure we have enough data
    if len(candles) < 15:
        print("Not enough data to plot. Please choose a larger time frame or a smaller interval.")
        return

    # Calculate Volume Profile
    bin_size = 0.1  # Adjust bin size as needed
    bin_centers, volume_profile = calculate_volume_profile(
        candles,
        bin_size=bin_size,
        discount_old_candles=True  # Set to True to discount older candles logarithmically
    )

    # Plot Volume Profile
    plot_volume_profile(bin_centers, volume_profile)

    # Calculate All Shadow Indices
    window_size = 14  # Moving average window size
    try:
        indices, dates, dates_numeric, adjusted_candles = calculate_all_shadow_indices(candles, window_size)
    except ValueError as e:
        print(e)
        return

    # Plot Candles and All Shadow Indices
    plot_candles_and_all_shadow_indices(
        dates,
        dates_numeric,
        adjusted_candles,
        indices
    )

if __name__ == "__main__":
    asyncio.run(main())
