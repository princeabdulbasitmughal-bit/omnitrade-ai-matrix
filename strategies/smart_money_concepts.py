import pandas as pd
import numpy as np
from typing import Dict, Any, List

class SmartMoneyConcepts:
    @staticmethod
    def detect_fvg(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detects Fair Value Gaps (FVGs) / Imbalances in 3-candle patterns.
        - Bullish FVG: Candle 1 High < Candle 3 Low (Gap in between)
        - Bearish FVG: Candle 1 Low > Candle 3 High (Gap in between)
        """
        fvgs = []
        if len(df) < 5:
            return fvgs

        for i in range(2, len(df)):
            c1 = df.iloc[i - 2]
            c2 = df.iloc[i - 1]
            c3 = df.iloc[i]

            # Bullish FVG
            if c3["low"] > c1["high"]:
                gap_size = c3["low"] - c1["high"]
                gap_pct = (gap_size / c2["close"]) * 100
                if gap_pct > 0.05: # Significant gap
                    fvgs.append({
                        "type": "BULLISH_FVG",
                        "top": float(c3["low"]),
                        "bottom": float(c1["high"]),
                        "gap_size": round(float(gap_size), 4),
                        "gap_pct": round(float(gap_pct), 3),
                        "index": i,
                        "timestamp": str(c2["timestamp"]),
                    })

            # Bearish FVG
            elif c3["high"] < c1["low"]:
                gap_size = c1["low"] - c3["high"]
                gap_pct = (gap_size / c2["close"]) * 100
                if gap_pct > 0.05:
                    fvgs.append({
                        "type": "BEARISH_FVG",
                        "top": float(c1["low"]),
                        "bottom": float(c3["high"]),
                        "gap_size": round(float(gap_size), 4),
                        "gap_pct": round(float(gap_pct), 3),
                        "index": i,
                        "timestamp": str(c2["timestamp"]),
                    })

        return fvgs[-10:] # Return latest 10 FVGs

    @staticmethod
    def detect_order_blocks(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detects Institutional Order Blocks:
        - Bullish OB: Last down-close candle before a strong bullish impulsive move.
        - Bearish OB: Last up-close candle before a strong bearish impulsive move.
        """
        obs = []
        if len(df) < 10:
            return obs

        for i in range(2, len(df) - 1):
            curr = df.iloc[i]
            next_c = df.iloc[i + 1]

            # Bullish OB check
            if curr["close"] < curr["open"]: # Bearish candle
                if next_c["close"] > next_c["open"] and (next_c["close"] - next_c["open"]) > (curr["open"] - curr["close"]) * 1.5:
                    obs.append({
                        "type": "BULLISH_OB",
                        "high": float(curr["high"]),
                        "low": float(curr["low"]),
                        "mitigated": False,
                        "index": i,
                        "timestamp": str(curr["timestamp"]),
                    })

            # Bearish OB check
            elif curr["close"] > curr["open"]: # Bullish candle
                if next_c["close"] < next_c["open"] and (next_c["open"] - next_c["close"]) > (curr["close"] - curr["open"]) * 1.5:
                    obs.append({
                        "type": "BEARISH_OB",
                        "high": float(curr["high"]),
                        "low": float(curr["low"]),
                        "mitigated": False,
                        "index": i,
                        "timestamp": str(curr["timestamp"]),
                    })

        return obs[-8:]

    @staticmethod
    def detect_structure_and_liquidity(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detects Swing Highs, Swing Lows, Liquidity Sweeps, and BOS / CHoCH.
        """
        if len(df) < 20:
            return {"market_structure": "UNKNOWN", "liquidity_sweep": None, "swing_highs": [], "swing_lows": []}

        # Identify swing highs and lows (5-candle window)
        highs = []
        lows = []
        for i in range(2, len(df) - 2):
            if df["high"].iloc[i] > df["high"].iloc[i-1] and df["high"].iloc[i] > df["high"].iloc[i-2] and \
               df["high"].iloc[i] > df["high"].iloc[i+1] and df["high"].iloc[i] > df["high"].iloc[i+2]:
                highs.append(float(df["high"].iloc[i]))

            if df["low"].iloc[i] < df["low"].iloc[i-1] and df["low"].iloc[i] < df["low"].iloc[i-2] and \
               df["low"].iloc[i] < df["low"].iloc[i+1] and df["low"].iloc[i] < df["low"].iloc[i+2]:
                lows.append(float(df["low"].iloc[i]))

        latest_close = float(df["close"].iloc[-1])
        latest_high = float(df["high"].iloc[-1])
        latest_low = float(df["low"].iloc[-1])

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
            "swing_highs_count": len(highs),
            "swing_lows_count": len(lows),
        }

    @staticmethod
    def get_smc_summary(df: pd.DataFrame) -> Dict[str, Any]:
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
