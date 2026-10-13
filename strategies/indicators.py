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
        Accepts DataFrame with ['open', 'high', 'low', 'close', 'volume'].
        Safely handles small or empty DataFrames and eliminates NaN propagation.
        """
        if df is None or df.empty:
            return pd.DataFrame() if df is None else df.copy()

        df = df.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = df["close"] if "close" in df.columns and col != "volume" else (1.0 if col == "volume" else 0.0)
            df[col] = pd.to_numeric(df[col], errors="coerce").ffill().bfill().fillna(0.0)

        n = len(df)
        closes = df["close"]
        highs = df["high"]
        lows = df["low"]
        vols = df["volume"]

        # 1. Exponential Moving Averages (EMA)
        df["ema_9"] = closes.ewm(span=min(9, max(1, n)), adjust=False).mean()
        df["ema_20"] = closes.ewm(span=min(20, max(1, n)), adjust=False).mean()
        df["ema_50"] = closes.ewm(span=min(50, max(1, n)), adjust=False).mean()
        df["ema_200"] = closes.ewm(span=min(200, max(1, n)), adjust=False).mean()

        # 2. Relative Strength Index (RSI)
        delta = closes.diff().fillna(0.0)
        gain = delta.where(delta > 0, 0.0).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        rsi = np.where((loss == 0) & (gain > 0), 100.0, np.where((loss == 0) & (gain == 0), 50.0, rsi))
        df["rsi"] = pd.Series(rsi, index=df.index).fillna(50.0).clip(0.0, 100.0)

        # 3. MACD (Moving Average Convergence Divergence)
        ema_12 = closes.ewm(span=min(12, max(1, n)), adjust=False).mean()
        ema_26 = closes.ewm(span=min(26, max(1, n)), adjust=False).mean()
        df["macd"] = (ema_12 - ema_26).fillna(0.0)
        df["macd_signal"] = df["macd"].ewm(span=min(9, max(1, n)), adjust=False).mean().fillna(0.0)
        df["macd_hist"] = (df["macd"] - df["macd_signal"]).fillna(0.0)

        # 4. Bollinger Bands
        bb_sma = closes.rolling(window=20, min_periods=1).mean()
        bb_std = closes.rolling(window=20, min_periods=1).std().fillna(0.0)
        df["bb_upper"] = (bb_sma + (bb_std * 2.0)).fillna(closes)
        df["bb_lower"] = (bb_sma - (bb_std * 2.0)).fillna(closes)
        df["bb_middle"] = bb_sma.fillna(closes)
        bb_range = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
        df["bb_pct"] = ((closes - df["bb_lower"]) / bb_range).fillna(0.5)

        # 5. Average True Range (ATR)
        high_low = (highs - lows).abs()
        prev_close = closes.shift(1).fillna(closes)
        high_close = (highs - prev_close).abs()
        low_close = (lows - prev_close).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        fallback_atr = (closes * 0.01).replace(0, 1e-4)
        df["atr"] = tr.rolling(window=14, min_periods=1).mean().bfill().fillna(fallback_atr)
        df["atr"] = np.where(df["atr"] <= 0, fallback_atr, df["atr"])

        # 6. VWAP (Volume Weighted Average Price)
        typical_price = (highs + lows + closes) / 3.0
        cum_vol = vols.cumsum().replace(0, np.nan)
        df["vwap"] = ((typical_price * vols).cumsum() / cum_vol).bfill().fillna(closes)

        # 7. SuperTrend (10, 3) using fast warning-free numpy arrays
        hl2 = ((highs + lows) / 2.0).to_numpy(dtype=float)
        atr_arr = df["atr"].to_numpy(dtype=float)
        close_arr = closes.to_numpy(dtype=float)
        upper_band = hl2 + (3.0 * atr_arr)
        lower_band = hl2 - (3.0 * atr_arr)
        supertrend = np.ones(n, dtype=bool)  # True = Uptrend, False = Downtrend

        for i in range(1, n):
            if close_arr[i] > upper_band[i - 1]:
                supertrend[i] = True
            elif close_arr[i] < lower_band[i - 1]:
                supertrend[i] = False
            else:
                supertrend[i] = supertrend[i - 1]
                if supertrend[i] and lower_band[i] < lower_band[i - 1]:
                    lower_band[i] = lower_band[i - 1]
                if not supertrend[i] and upper_band[i] > upper_band[i - 1]:
                    upper_band[i] = upper_band[i - 1]

        df["supertrend_dir"] = supertrend
        df["supertrend_upper"] = upper_band
        df["supertrend_lower"] = lower_band

        # 8. Stochastic RSI
        min_rsi = df["rsi"].rolling(window=14, min_periods=1).min()
        max_rsi = df["rsi"].rolling(window=14, min_periods=1).max()
        rsi_range = (max_rsi - min_rsi).replace(0, np.nan)
        stoch = ((df["rsi"] - min_rsi) / rsi_range).fillna(0.5)
        df["stoch_rsi_k"] = (stoch.rolling(window=3, min_periods=1).mean() * 100.0).fillna(50.0)
        df["stoch_rsi_d"] = df["stoch_rsi_k"].rolling(window=3, min_periods=1).mean().fillna(50.0)

        return df

    @staticmethod
    def get_latest_summary(df: pd.DataFrame) -> Dict[str, Any]:
        """Extracts the latest snapshot of all technical indicators."""
        if df is None or df.empty:
            return {
                "close": 0.0,
                "ema_9": 0.0,
                "ema_20": 0.0,
                "ema_50": 0.0,
                "ema_200": 0.0,
                "rsi": 50.0,
                "macd": 0.0,
                "macd_signal": 0.0,
                "macd_hist": 0.0,
                "bb_upper": 0.0,
                "bb_lower": 0.0,
                "bb_pct": 0.5,
                "atr": 0.0,
                "vwap": 0.0,
                "supertrend_is_bull": True,
                "stoch_k": 50.0,
                "stoch_d": 50.0,
                "is_golden_cross": False,
                "is_death_cross": False,
            }

        df_calc = TechnicalIndicators.compute_all(df)
        last = df_calc.iloc[-1]
        prev = df_calc.iloc[-2] if len(df_calc) > 1 else last

        def _safe_float(val: Any, default: float = 0.0) -> float:
            try:
                f = float(val)
                return default if np.isnan(f) or np.isinf(f) else f
            except Exception:
                return default

        return {
            "close": _safe_float(last.get("close", 0.0)),
            "ema_9": _safe_float(last.get("ema_9", 0.0)),
            "ema_20": _safe_float(last.get("ema_20", 0.0)),
            "ema_50": _safe_float(last.get("ema_50", 0.0)),
            "ema_200": _safe_float(last.get("ema_200", 0.0)),
            "rsi": round(_safe_float(last.get("rsi", 50.0), 50.0), 2),
            "macd": round(_safe_float(last.get("macd", 0.0)), 4),
            "macd_signal": round(_safe_float(last.get("macd_signal", 0.0)), 4),
            "macd_hist": round(_safe_float(last.get("macd_hist", 0.0)), 4),
            "bb_upper": round(_safe_float(last.get("bb_upper", 0.0)), 2),
            "bb_lower": round(_safe_float(last.get("bb_lower", 0.0)), 2),
            "bb_pct": round(_safe_float(last.get("bb_pct", 0.5), 0.5), 2),
            "atr": round(_safe_float(last.get("atr", 0.0)), 4),
            "vwap": round(_safe_float(last.get("vwap", 0.0)), 2),
            "supertrend_is_bull": bool(last.get("supertrend_dir", True)),
            "stoch_k": round(_safe_float(last.get("stoch_rsi_k", 50.0), 50.0), 2),
            "stoch_d": round(_safe_float(last.get("stoch_rsi_d", 50.0), 50.0), 2),
            "is_golden_cross": bool(prev["ema_50"] <= prev["ema_200"] and last["ema_50"] > last["ema_200"]),
            "is_death_cross": bool(prev["ema_50"] >= prev["ema_200"] and last["ema_50"] < last["ema_200"]),
        }

    @classmethod
    def generate_signal(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Generates a standardized trading signal from technical indicators."""
        summary = cls.get_latest_summary(df)
        if df is None or df.empty:
            return {**summary, "strategy": "TechnicalIndicators", "signal": "HOLD", "action": "HOLD", "confidence": 0.0}

        st_bull = summary["supertrend_is_bull"]
        macd_hist = summary["macd_hist"]
        rsi = summary["rsi"]

        if st_bull and macd_hist > 0 and rsi < 72:
            sig = "BUY"
            conf = 0.76
        elif not st_bull and macd_hist < 0 and rsi > 28:
            sig = "SELL"
            conf = 0.76
        else:
            sig = "HOLD"
            conf = 0.52

        return {
            **summary,
            "strategy": "TechnicalIndicators",
            "signal": sig,
            "action": sig,
            "confidence": conf,
        }

    calculate_signals = generate_signal
    get_signal = generate_signal
    evaluate = generate_signal

