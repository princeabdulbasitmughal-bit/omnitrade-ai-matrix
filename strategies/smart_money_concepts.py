import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

class SmartMoneyConcepts:
    @staticmethod
    def detect_fvg(df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Detects Fair Value Gaps (FVGs) / Imbalances in 3-candle patterns.
        - Bullish FVG: Candle 1 High < Candle 3 Low (Gap in between)
        - Bearish FVG: Candle 1 Low > Candle 3 High (Gap in between)
        """
        fvgs: List[Dict[str, Any]] = []
        if df is None or df.empty or len(df) < 3:
            return fvgs
        if not all(c in df.columns for c in ["high", "low", "close"]):
            return fvgs

        for i in range(2, len(df)):
            c1 = df.iloc[i - 2]
            c2 = df.iloc[i - 1]
            c3 = df.iloc[i]

            c1_high, c1_low = float(c1["high"]), float(c1["low"])
            c2_close = float(c2["close"])
            c3_high, c3_low = float(c3["high"]), float(c3["low"])

            if any(np.isnan(v) for v in (c1_high, c1_low, c2_close, c3_high, c3_low)) or c2_close <= 0:
                continue

            ts_str = str(c2["timestamp"]) if "timestamp" in df.columns else str(c2.name)

            # Bullish FVG
            if c3_low > c1_high:
                gap_size = c3_low - c1_high
                gap_pct = (gap_size / c2_close) * 100.0
                if gap_pct > 0.05:  # Significant gap
                    fvgs.append({
                        "type": "BULLISH_FVG",
                        "top": float(c3_low),
                        "bottom": float(c1_high),
                        "gap_size": round(float(gap_size), 4),
                        "gap_pct": round(float(gap_pct), 3),
                        "index": i,
                        "timestamp": ts_str,
                    })

            # Bearish FVG
            elif c3_high < c1_low:
                gap_size = c1_low - c3_high
                gap_pct = (gap_size / c2_close) * 100.0
                if gap_pct > 0.05:
                    fvgs.append({
                        "type": "BEARISH_FVG",
                        "top": float(c1_low),
                        "bottom": float(c3_high),
                        "gap_size": round(float(gap_size), 4),
                        "gap_pct": round(float(gap_pct), 3),
                        "index": i,
                        "timestamp": ts_str,
                    })

        return fvgs[-10:]  # Return latest 10 FVGs

    @staticmethod
    def detect_order_blocks(df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Detects Institutional Order Blocks:
        - Bullish OB: Last down-close candle before a strong bullish impulsive move.
        - Bearish OB: Last up-close candle before a strong bearish impulsive move.
        """
        obs: List[Dict[str, Any]] = []
        if df is None or df.empty or len(df) < 4:
            return obs
        if not all(c in df.columns for c in ["open", "high", "low", "close"]):
            return obs

        for i in range(1, len(df) - 1):
            curr = df.iloc[i]
            next_c = df.iloc[i + 1]

            c_open, c_high, c_low, c_close = float(curr["open"]), float(curr["high"]), float(curr["low"]), float(curr["close"])
            n_open, n_close = float(next_c["open"]), float(next_c["close"])
            if any(np.isnan(v) for v in (c_open, c_high, c_low, c_close, n_open, n_close)):
                continue

            ts_str = str(curr["timestamp"]) if "timestamp" in df.columns else str(curr.name)

            # Bullish OB check
            if c_close < c_open:  # Bearish candle
                if n_close > n_open and (n_close - n_open) > (c_open - c_close) * 1.5:
                    obs.append({
                        "type": "BULLISH_OB",
                        "high": float(c_high),
                        "low": float(c_low),
                        "mitigated": False,
                        "index": i,
                        "timestamp": ts_str,
                    })

            # Bearish OB check
            elif c_close > c_open:  # Bullish candle
                if n_close < n_open and (n_open - n_close) > (c_close - c_open) * 1.5:
                    obs.append({
                        "type": "BEARISH_OB",
                        "high": float(c_high),
                        "low": float(c_low),
                        "mitigated": False,
                        "index": i,
                        "timestamp": ts_str,
                    })

        return obs[-8:]

    @staticmethod
    def detect_structure_and_liquidity(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """
        Detects Swing Highs, Swing Lows, Liquidity Sweeps, and BOS / CHoCH.
        Safely handles small or empty DataFrames with consistent return keys.
        """
        if df is None or df.empty or not all(c in df.columns for c in ["high", "low", "close"]):
            return {
                "market_structure": "UNKNOWN",
                "liquidity_sweep": None,
                "recent_swing_high": 0.0,
                "recent_swing_low": 0.0,
                "swing_highs": [],
                "swing_lows": [],
                "swing_highs_count": 0,
                "swing_lows_count": 0,
            }

        high_s = pd.to_numeric(df["high"], errors="coerce").dropna()
        low_s = pd.to_numeric(df["low"], errors="coerce").dropna()
        close_s = pd.to_numeric(df["close"], errors="coerce").dropna()

        if high_s.empty or low_s.empty or close_s.empty:
            return {
                "market_structure": "UNKNOWN",
                "liquidity_sweep": None,
                "recent_swing_high": 0.0,
                "recent_swing_low": 0.0,
                "swing_highs": [],
                "swing_lows": [],
                "swing_highs_count": 0,
                "swing_lows_count": 0,
            }

        if len(df) < 20:
            max_h = float(high_s.max())
            min_l = float(low_s.min())
            return {
                "market_structure": "UNKNOWN",
                "liquidity_sweep": None,
                "recent_swing_high": max_h,
                "recent_swing_low": min_l,
                "swing_highs": [max_h],
                "swing_lows": [min_l],
                "swing_highs_count": 1,
                "swing_lows_count": 1,
            }

        # Identify swing highs and lows (5-candle window)
        highs = []
        lows = []
        for i in range(2, len(df) - 2):
            h_i = float(df["high"].iloc[i])
            l_i = float(df["low"].iloc[i])
            if not np.isnan(h_i) and h_i > df["high"].iloc[i-1] and h_i > df["high"].iloc[i-2] and \
               h_i > df["high"].iloc[i+1] and h_i > df["high"].iloc[i+2]:
                highs.append(h_i)

            if not np.isnan(l_i) and l_i < df["low"].iloc[i-1] and l_i < df["low"].iloc[i-2] and \
               l_i < df["low"].iloc[i+1] and l_i < df["low"].iloc[i+2]:
                lows.append(l_i)

        latest_close = float(close_s.iloc[-1])
        latest_high = float(high_s.iloc[-1])
        latest_low = float(low_s.iloc[-1])

        # Market structure
        structure = "RANGING"
        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                structure = "BULLISH_TREND (Higher Highs / Higher Lows)"
            elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                structure = "BEARISH_TREND (Lower Highs / Lower Lows)"

        # Liquidity sweep detection
        liquidity_sweep = None
        if highs and latest_high > highs[-1] and latest_close < highs[-1]:
            liquidity_sweep = "BEARISH_BUY_SIDE_LIQUIDITY_SWEEP (Fakeout above swing high)"
        elif lows and latest_low < lows[-1] and latest_close > lows[-1]:
            liquidity_sweep = "BULLISH_SELL_SIDE_LIQUIDITY_SWEEP (Fakeout below swing low)"

        return {
            "market_structure": structure,
            "liquidity_sweep": liquidity_sweep,
            "recent_swing_high": highs[-1] if highs else latest_high,
            "recent_swing_low": lows[-1] if lows else latest_low,
            "swing_highs": highs,
            "swing_lows": lows,
            "swing_highs_count": len(highs),
            "swing_lows_count": len(lows),
        }

    @staticmethod
    def get_smc_summary(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """Provides full SMC analytical summary."""
        fvgs = SmartMoneyConcepts.detect_fvg(df)
        obs = SmartMoneyConcepts.detect_order_blocks(df)
        struct = SmartMoneyConcepts.detect_structure_and_liquidity(df)

        bullish_fvg_active = any(f["type"] == "BULLISH_FVG" for f in fvgs[-3:]) if fvgs else False
        bearish_fvg_active = any(f["type"] == "BEARISH_FVG" for f in fvgs[-3:]) if fvgs else False

        return {
            "market_structure": struct["market_structure"],
            "liquidity_sweep": struct["liquidity_sweep"],
            "recent_swing_high": struct["recent_swing_high"],
            "recent_swing_low": struct["recent_swing_low"],
            "active_fvgs_count": len(fvgs),
            "active_obs_count": len(obs),
            "bullish_fvg_present": bullish_fvg_active,
            "bearish_fvg_present": bearish_fvg_active,
            "latest_fvg": fvgs[-1] if fvgs else None,
            "latest_ob": obs[-1] if obs else None,
        }

    @classmethod
    def generate_signal(cls, df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """Generates a standardized trading signal from SMC structure, FVGs, and Order Blocks."""
        summary = cls.get_smc_summary(df)
        if df is None or df.empty:
            return {**summary, "strategy": "SmartMoneyConcepts", "signal": "HOLD", "action": "HOLD", "confidence": 0.0}

        struct = summary["market_structure"]
        sweep = summary["liquidity_sweep"] or ""
        bull_fvg = summary["bullish_fvg_present"]
        bear_fvg = summary["bearish_fvg_present"]

        if "BULLISH" in struct or "BULLISH" in sweep or bull_fvg:
            sig = "BUY"
            conf = 0.80 if ("BULLISH" in struct and bull_fvg) else 0.72
        elif "BEARISH" in struct or "BEARISH" in sweep or bear_fvg:
            sig = "SELL"
            conf = 0.80 if ("BEARISH" in struct and bear_fvg) else 0.72
        else:
            sig = "HOLD"
            conf = 0.50

        return {
            **summary,
            "strategy": "SmartMoneyConcepts",
            "signal": sig,
            "action": sig,
            "confidence": conf,
        }

    calculate_signals = generate_signal
    get_signal = generate_signal
    evaluate = generate_signal
    predict = generate_signal

