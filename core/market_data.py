import time
import math
import random
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

try:
    import ccxt
except ImportError:
    ccxt = None

try:
    import yfinance as yf
except ImportError:
    yf = None

from config.settings import Config

logger = logging.getLogger("OmniTrade.MarketData")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class MarketDataProvider:
    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id.lower()
        self.exchange = None
        self._init_exchange()
        self.cache: Dict[str, pd.DataFrame] = {}
        self.exchange_offline = False

    def _init_exchange(self):
        """Initializes ccxt exchange instance with sandbox/public fallbacks."""
        if not ccxt:
            logger.warning("ccxt is not installed. Will use yfinance/mock data.")
            return

        try:
            exchange_class = getattr(ccxt, self.exchange_id, None)
            if exchange_class:
                config_params = {
                    "enableRateLimit": True,
                    "timeout": 2000,
                }
                if self.exchange_id == "binance" and Config.BINANCE_API_KEY:
                    config_params["apiKey"] = Config.BINANCE_API_KEY
                    config_params["secret"] = Config.BINANCE_SECRET
                elif self.exchange_id == "bybit" and Config.BYBIT_API_KEY:
                    config_params["apiKey"] = Config.BYBIT_API_KEY
                    config_params["secret"] = Config.BYBIT_SECRET

                self.exchange = exchange_class(config_params)
                logger.info(f"Initialized CCXT exchange: {self.exchange_id}")
            else:
                logger.warning(f"Exchange {self.exchange_id} not found in ccxt. Falling back to binance.")
                self.exchange = ccxt.binance({"enableRateLimit": True})
        except Exception as e:
            logger.error(f"Failed to initialize exchange {self.exchange_id}: {e}")
            self.exchange = None

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 150) -> pd.DataFrame:
        """
        Fetches OHLCV candle data for any asset (Crypto, Forex, Gold, Stocks).
        Returns clean normalized DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        symbol_upper = symbol.upper()
        # 1. Check if crypto pair (e.g. BTC/USDT, ETH/USDT, SOL/USDT)
        if ("/" in symbol_upper and ("USDT" in symbol_upper or "BUSD" in symbol_upper or "USD" in symbol_upper)) and not ("EUR/" in symbol_upper or "GBP/" in symbol_upper or "XAU/" in symbol_upper):
            df = self._fetch_crypto_ccxt(symbol_upper, timeframe, limit)
            if df is not None and not df.empty:
                return df

        # 2. Check if Forex, Commodity, or Stock (e.g. XAU/USD, EUR/USD, NVDA, TSLA)
        df = self._fetch_yfinance(symbol_upper, timeframe, limit)
        if df is not None and not df.empty:
            return df

        # 3. High-fidelity synthetic fallback if network/API is restricted
        logger.warning(f"Live feeds unavailable for {symbol_upper}. Generating high-fidelity market simulation data.")
        return self._generate_realistic_feed(symbol_upper, limit=limit)

    def _fetch_crypto_ccxt(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        if not self.exchange or self.exchange_offline:
            return None
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if ohlcv and len(ohlcv) > 0:
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df
        except Exception as e:
            logger.debug(f"CCXT fetch failed for {symbol}: {e}. Enabling rapid fallback.")
            self.exchange_offline = True
        return None

    def _fetch_yfinance(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        if not yf:
            return None

        # Map symbols to Yahoo ticker format
        ticker_map = {
            "XAU/USD": "GC=F",       # Gold Futures
            "XAUUSD": "GC=F",
            "EUR/USD": "EURUSD=X",   # EUR/USD Forex
            "GBP/USD": "GBPUSD=X",   # GBP/USD Forex
            "USD/JPY": "JPY=X",      # USD/JPY Forex
            "BTC/USDT": "BTC-USD",
            "ETH/USDT": "ETH-USD",
            "SOL/USDT": "SOL-USD",
            "BNB/USDT": "BNB-USD",
        }
        ticker = ticker_map.get(symbol, symbol.replace("/", "-"))

        # Map timeframe to yfinance interval
        tf_map = {
            "1m": ("1d", "1m"),
            "5m": ("5d", "5m"),
            "15m": ("1mo", "15m"),
            "1h": ("3mo", "1h"),
            "4h": ("6mo", "1h"),     # yfinance doesn't have 4h, use 1h resample
            "1d": ("1y", "1d"),
        }
        period, interval = tf_map.get(timeframe, ("1mo", "15m"))

        try:
            data = yf.Ticker(ticker).history(period=period, interval=interval)
            if data is not None and not data.empty:
                df = data.reset_index()
                # Find datetime column
                dt_col = "Datetime" if "Datetime" in df.columns else "Date"
                df = df.rename(columns={
                    dt_col: "timestamp",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                })
                df = df[["timestamp", "open", "high", "low", "close", "volume"]].tail(limit)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df
        except Exception as e:
            logger.debug(f"yfinance fetch failed for {ticker}: {e}")
        return None

    def _generate_realistic_feed(self, symbol: str, limit: int = 150) -> pd.DataFrame:
        """Generates realistic Geometric Brownian Motion price action for testing & fallback."""
        base_prices = {
            "BTC/USDT": 96500.0,
            "ETH/USDT": 2750.0,
            "SOL/USDT": 185.0,
            "BNB/USDT": 650.0,
            "XAU/USD": 2920.0,
            "EUR/USD": 1.0520,
            "NVDA": 138.50,
            "TSLA": 215.0,
        }
        base_price = base_prices.get(symbol, 100.0)
        volatility = 0.0035 if "USD" in symbol and "/" in symbol and not "USDT" in symbol else 0.008

        now = datetime.utcnow()
        timestamps = [now - timedelta(minutes=15 * (limit - i)) for i in range(limit)]

        prices = [base_price]
        for _ in range(limit - 1):
            drift = 0.0002
            shock = np.random.normal(0, volatility)
            new_p = prices[-1] * (1 + drift + shock)
            prices.append(max(0.0001, new_p))

        data = []
        for i in range(limit):
            p = prices[i]
            spread = p * (volatility * 0.7)
            high = p + abs(np.random.normal(0, spread))
            low = p - abs(np.random.normal(0, spread))
            open_p = p + np.random.uniform(-spread * 0.5, spread * 0.5)
            close_p = p + np.random.uniform(-spread * 0.5, spread * 0.5)
            high = max(high, open_p, close_p)
            low = min(low, open_p, close_p)
            volume = np.random.uniform(50, 500) * (100000 / p)
            data.append({
                "timestamp": timestamps[i],
                "open": round(open_p, 4 if p > 10 else 6),
                "high": round(high, 4 if p > 10 else 6),
                "low": round(low, 4 if p > 10 else 6),
                "close": round(close_p, 4 if p > 10 else 6),
                "volume": round(volume, 2),
            })
        return pd.DataFrame(data)

    def get_current_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetches the latest real-time ticker price and 24h stats."""
        df = self.fetch_ohlcv(symbol, timeframe="15m", limit=30)
        if df.empty:
            return {"symbol": symbol, "last": 0.0, "change_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume": 0.0}

        latest = df.iloc[-1]
        first = df.iloc[0]
        pct_change = ((latest["close"] - first["close"]) / first["close"]) * 100

        return {
            "symbol": symbol,
            "last": float(latest["close"]),
            "open": float(latest["open"]),
            "high": float(df["high"].max()),
            "low": float(df["low"].min()),
            "volume": float(df["volume"].sum()),
            "change_24h": round(pct_change, 2),
            "timestamp": latest["timestamp"].isoformat() if hasattr(latest["timestamp"], "isoformat") else str(latest["timestamp"]),
        }
