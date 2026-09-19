import pandas as pd
import numpy as np
from typing import Dict, Any

try:
    import ta
except ImportError:
    ta = None

class TechnicalIndicators:
    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes the complete multi-indicator technical analysis matrix.
        Accepts DataFrame with ['open', 'high', 'low', 'close', 'volume']
        """
        if df.empty or len(df) < 15:
            return df

        df = df.copy()

        # 1. Exponential Moving Averages (EMA)
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_200"] = df["close"].ewm(span=min(200, len(df)), adjust=False).mean()

        # 2. Relative Strength Index (RSI)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))
        df["rsi"] = df["rsi"].fillna(50.0)

        # 3. MACD (Moving Average Convergence Divergence)
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # 4. Bollinger Bands
        bb_sma = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper"] = bb_sma + (bb_std * 2)
        df["bb_lower"] = bb_sma - (bb_std * 2)
        df["bb_middle"] = bb_sma
        df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)

        # 5. Average True Range (ATR)
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean().bfill()

        # 6. VWAP (Volume Weighted Average Price)
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum().replace(0, np.nan)
        df["vwap"] = df["vwap"].bfill()

        # 7. SuperTrend (10, 3)
        hl2 = (df["high"] + df["low"]) / 2.0
        upper_band = hl2 + (3.0 * df["atr"])
        lower_band = hl2 - (3.0 * df["atr"])
        supertrend = [True] * len(df) # True = Uptrend, False = Downtrend

        for i in range(1, len(df)):
            if df["close"].iloc[i] > upper_band.iloc[i - 1]:
                supertrend[i] = True
            elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
                supertrend[i] = False
            else:
                supertrend[i] = supertrend[i - 1]
                if supertrend[i] and lower_band.iloc[i] < lower_band.iloc[i - 1]:
                    lower_band.iloc[i] = lower_band.iloc[i - 1]
                if not supertrend[i] and upper_band.iloc[i] > upper_band.iloc[i - 1]:
                    upper_band.iloc[i] = upper_band.iloc[i - 1]

        df["supertrend_dir"] = supertrend
        df["supertrend_upper"] = upper_band
        df["supertrend_lower"] = lower_band

        # 8. Stochastic RSI
        min_rsi = df["rsi"].rolling(window=14).min()
        max_rsi = df["rsi"].rolling(window=14).max()
        stoch = (df["rsi"] - min_rsi) / (max_rsi - min_rsi).replace(0, np.nan)
        df["stoch_rsi_k"] = stoch.rolling(window=3).mean() * 100
        df["stoch_rsi_d"] = df["stoch_rsi_k"].rolling(window=3).mean()

        return df

    @staticmethod
    def get_latest_summary(df: pd.DataFrame) -> Dict[str, Any]:
        """Extracts the latest snapshot of all technical indicators."""
        if df.empty:
            return {}

        df_calc = TechnicalIndicators.compute_all(df)
        last = df_calc.iloc[-1]
        prev = df_calc.iloc[-2] if len(df_calc) > 1 else last

        return {
            "close": float(last["close"]),
            "ema_9": float(last["ema_9"]),
            "ema_20": float(last["ema_20"]),
            "ema_50": float(last["ema_50"]),
            "ema_200": float(last["ema_200"]),
            "rsi": round(float(last["rsi"]), 2),
            "macd": round(float(last["macd"]), 4),
            "macd_signal": round(float(last["macd_signal"]), 4),
            "macd_hist": round(float(last["macd_hist"]), 4),
            "bb_upper": round(float(last["bb_upper"]), 2),
            "bb_lower": round(float(last["bb_lower"]), 2),
            "bb_pct": round(float(last["bb_pct"]), 2),
            "atr": round(float(last["atr"]), 4),
            "vwap": round(float(last["vwap"]), 2),
            "supertrend_is_bull": bool(last["supertrend_dir"]),
            "stoch_k": round(float(last.get("stoch_rsi_k", 50.0)), 2),
            "stoch_d": round(float(last.get("stoch_rsi_d", 50.0)), 2),
            "is_golden_cross": bool(prev["ema_50"] <= prev["ema_200"] and last["ema_50"] > last["ema_200"]),
            "is_death_cross": bool(prev["ema_50"] >= prev["ema_200"] and last["ema_50"] < last["ema_200"]),
        }
