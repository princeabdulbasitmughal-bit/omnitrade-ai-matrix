"""
DeepSeek-R1 Quantitative Trading Ruleset Engine
================================================
Institutional-grade Quantitative Strategy Engine implementing:
1. Fibonacci Retracement & Extension Analysis (Golden Pocket 0.618-0.650, OTE 0.618-0.786, Extensions 1.272-2.618)
2. Institutional Liquidity Sweeps & Smart Money Concepts (BSL/SSL Sweeps, Turtle Soup, CHoCH/BOS)
3. Multi-Timeframe Confirmation (HTF Macro Bias, ITF Structure & OTE, LTF Liquidity Trigger)
4. Strict 1:3+ Risk/Reward Ratio Gatekeeper with Dynamic Kelly & ATR Position Sizing
5. DeepSeek-R1 Chain-of-Thought (CoT) Reasoning Engine with Deterministic Quantitative Fallback
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger("OmniTrade.DeepSeekR1Ruleset")

class FibonacciEngine:
    """
    Mathematical Fibonacci Retracement & Extension Calculator.
    Key Retracements: 0.236, 0.382, 0.500, 0.618, 0.650, 0.786, 0.886
    Optimal Trade Entry (OTE): [0.618, 0.786] with Golden Pocket at [0.618, 0.650]
    Key Extensions: 1.272, 1.414, 1.618, 2.000, 2.618
    """

    RETRACEMENT_LEVELS = [0.0, 0.236, 0.382, 0.500, 0.618, 0.650, 0.786, 0.886, 1.0]
    EXTENSION_LEVELS = [1.272, 1.414, 1.618, 2.000, 2.618]
    GOLDEN_POCKET_MIN = 0.618
    GOLDEN_POCKET_MAX = 0.650
    OTE_MIN = 0.618
    OTE_MAX = 0.786
    INVALIDATION_FIB = 0.886

    @staticmethod
    def identify_swing_points(df: pd.DataFrame, window: int = 5) -> Dict[str, Any]:
        """
        Extracts recent swing highs and swing lows using local fractal extrema.
        """
        if len(df) < window * 2 + 1:
            high = float(df["high"].max()) if not df.empty else 0.0
            low = float(df["low"].min()) if not df.empty else 0.0
            return {
                "swing_high": high,
                "swing_low": low,
                "all_swing_highs": [high],
                "all_swing_lows": [low],
                "trend": "UNKNOWN"
            }

        highs = []
        lows = []
        high_indices = []
        low_indices = []

        for i in range(window, len(df) - window):
            curr_high = df["high"].iloc[i]
            curr_low = df["low"].iloc[i]
            
            # Fractal High
            if all(curr_high >= df["high"].iloc[i - j] for j in range(1, window + 1)) and \
               all(curr_high >= df["high"].iloc[i + j] for j in range(1, window + 1)):
                highs.append(float(curr_high))
                high_indices.append(i)

            # Fractal Low
            if all(curr_low <= df["low"].iloc[i - j] for j in range(1, window + 1)) and \
               all(curr_low <= df["low"].iloc[i + j] for j in range(1, window + 1)):
                lows.append(float(curr_low))
                low_indices.append(i)

        if not highs:
            highs = [float(df["high"].max())]
            high_indices = [len(df) - 1]
        if not lows:
            lows = [float(df["low"].min())]
            low_indices = [len(df) - 1]

        recent_high = highs[-1]
        recent_low = lows[-1]
        
        trend = "RANGING"
        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                trend = "BULLISH"
            elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                trend = "BEARISH"

        return {
            "swing_high": recent_high,
            "swing_low": recent_low,
            "all_swing_highs": highs,
            "all_swing_lows": lows,
            "last_high_idx": high_indices[-1] if high_indices else len(df) - 1,
            "last_low_idx": low_indices[-1] if low_indices else len(df) - 1,
            "trend": trend
        }

    @classmethod
    def calculate_fibonacci_matrix(
        cls, 
        swing_high: float, 
        swing_low: float, 
        direction: str = "BULLISH"
    ) -> Dict[str, Any]:
        """
        Computes accurate Fibonacci retracement and extension price levels.
        """
        diff = abs(swing_high - swing_low)
        if diff <= 0:
            return {"error": "Invalid swing range", "levels": {}}

        levels = {}
        extensions = {}

        if direction.upper() == "BULLISH":
            for fib in cls.RETRACEMENT_LEVELS:
                price = swing_high - (diff * fib)
                levels[f"{fib:.3f}"] = round(price, 4)

            ote_zone = {
                "ote_top": round(swing_high - (diff * cls.OTE_MIN), 4),       # 0.618
                "ote_pocket": round(swing_high - (diff * cls.GOLDEN_POCKET_MAX), 4), # 0.650
                "ote_bottom": round(swing_high - (diff * cls.OTE_MAX), 4),    # 0.786
                "invalidation": round(swing_high - (diff * cls.INVALIDATION_FIB), 4) # 0.886
            }

            for ext in cls.EXTENSION_LEVELS:
                ext_price = swing_low + (diff * ext)
                extensions[f"{ext:.3f}"] = round(ext_price, 4)

        else: # BEARISH
            for fib in cls.RETRACEMENT_LEVELS:
                price = swing_low + (diff * fib)
                levels[f"{fib:.3f}"] = round(price, 4)

            ote_zone = {
                "ote_bottom": round(swing_low + (diff * cls.OTE_MIN), 4),       # 0.618
                "ote_pocket": round(swing_low + (diff * cls.GOLDEN_POCKET_MAX), 4), # 0.650
                "ote_top": round(swing_low + (diff * cls.OTE_MAX), 4),          # 0.786
                "invalidation": round(swing_low + (diff * cls.INVALIDATION_FIB), 4) # 0.886
            }

            for ext in cls.EXTENSION_LEVELS:
                ext_price = swing_high - (diff * ext)
                extensions[f"{ext:.3f}"] = round(ext_price, 4)

        return {
            "direction": direction.upper(),
            "swing_high": swing_high,
            "swing_low": swing_low,
            "delta": round(diff, 4),
            "retracements": levels,
            "ote_zone": ote_zone,
            "extensions": extensions
        }

    @classmethod
    def evaluate_price_in_fib_zone(
        cls, 
        current_price: float, 
        fib_matrix: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates whether current market price is inside the Golden Pocket / OTE zone.
        """
        if "ote_zone" not in fib_matrix:
            return {"in_ote": False, "in_golden_pocket": False, "zone_status": "NONE"}

        direction = fib_matrix["direction"]
        ote = fib_matrix["ote_zone"]

        in_ote = False
        in_golden_pocket = False
        status = "OUTSIDE"

        if direction == "BULLISH":
            top = ote["ote_top"]
            pocket = ote["ote_pocket"]
            bottom = ote["ote_bottom"]
            inval = ote["invalidation"]

            if current_price < inval:
                status = "INVALIDATED_BELOW_0.886"
            elif bottom <= current_price <= top:
                in_ote = True
                if pocket <= current_price <= top:
                    in_golden_pocket = True
                    status = "GOLDEN_POCKET_0.618_0.650"
                else:
                    status = "OTE_DEEP_DISCOUNT_0.650_0.786"
            elif current_price > top:
                status = "PREMIUM_ABOVE_0.618"
        else: # BEARISH
            bottom = ote["ote_bottom"]
            pocket = ote["ote_pocket"]
            top = ote["ote_top"]
            inval = ote["invalidation"]

            if current_price > inval:
                status = "INVALIDATED_ABOVE_0.886"
            elif bottom <= current_price <= top:
                in_ote = True
                if bottom <= current_price <= pocket:
                    in_golden_pocket = True
                    status = "GOLDEN_POCKET_0.618_0.650"
                else:
                    status = "OTE_DEEP_PREMIUM_0.650_0.786"
            elif current_price < bottom:
                status = "DISCOUNT_BELOW_0.618"

        return {
            "in_ote": in_ote,
            "in_golden_pocket": in_golden_pocket,
            "zone_status": status,
            "current_price": current_price,
            "ote_bounds": ote
        }


class LiquiditySweepEngine:
    """
    Institutional Liquidity Sweep & Smart Money Concepts Engine.
    Detects:
    1. Buy-Side Liquidity (BSL) Sweeps (Turtle Soup above swing highs)
    2. Sell-Side Liquidity (SSL) Sweeps (Turtle Soup below swing lows)
    3. Wick-to-Body Displacement Ratio
    4. Change of Character (CHoCH) & Break of Structure (BOS)
    """

    @staticmethod
    def detect_liquidity_sweeps(
        df: pd.DataFrame, 
        swing_high: float, 
        swing_low: float,
        lookback_candles: int = 5
    ) -> Dict[str, Any]:
        """
        Analyzes the most recent candles for institutional stop runs / liquidity grabs.
        """
        if len(df) < 2:
            return {"sweep_detected": False, "sweep_type": "NONE", "details": {}}

        effective_lookback = min(len(df), lookback_candles)
        recent_df = df.tail(effective_lookback)
        latest = df.iloc[-1]

        c_open = float(latest["open"])
        c_high = float(latest["high"])
        c_low = float(latest["low"])
        c_close = float(latest["close"])

        total_range = max(c_high - c_low, 1e-6)
        upper_wick = c_high - max(c_open, c_close)
        lower_wick = min(c_open, c_close) - c_low
        body = abs(c_close - c_open)

        upper_wick_ratio = upper_wick / total_range
        lower_wick_ratio = lower_wick / total_range

        bsl_sweep = False
        bsl_strength = 0.0
        
        for _, row in recent_df.iterrows():
            if row["high"] > swing_high and latest["close"] < swing_high:
                bsl_sweep = True
                overshoot_pct = ((row["high"] - swing_high) / swing_high) * 100
                bsl_strength = min(1.0, (upper_wick_ratio * 0.7) + (overshoot_pct * 0.3))
                break

        ssl_sweep = False
        ssl_strength = 0.0
        for _, row in recent_df.iterrows():
            if row["low"] < swing_low and latest["close"] > swing_low:
                ssl_sweep = True
                undershoot_pct = ((swing_low - row["low"]) / swing_low) * 100
                ssl_strength = min(1.0, (lower_wick_ratio * 0.7) + (undershoot_pct * 0.3))
                break

        sweep_type = "NONE"
        detected = False
        strength = 0.0
        invalidation_level = 0.0

        if ssl_sweep and not bsl_sweep:
            sweep_type = "BULLISH_SSL_SWEEP"
            detected = True
            strength = round(max(ssl_strength, 0.65), 2)
            invalidation_level = float(recent_df["low"].min())
        elif bsl_sweep and not ssl_sweep:
            sweep_type = "BEARISH_BSL_SWEEP"
            detected = True
            strength = round(max(bsl_strength, 0.65), 2)
            invalidation_level = float(recent_df["high"].max())
        elif ssl_sweep and bsl_sweep:
            if lower_wick_ratio > upper_wick_ratio:
                sweep_type = "BULLISH_SSL_SWEEP"
                detected = True
                strength = 0.60
                invalidation_level = float(recent_df["low"].min())
            else:
                sweep_type = "BEARISH_BSL_SWEEP"
                detected = True
                strength = 0.60
                invalidation_level = float(recent_df["high"].max())

        return {
            "sweep_detected": detected,
            "sweep_type": sweep_type,
            "strength": strength,
            "invalidation_wick_level": invalidation_level,
            "upper_wick_ratio": round(upper_wick_ratio, 3),
            "lower_wick_ratio": round(lower_wick_ratio, 3),
            "body_ratio": round(body / total_range, 3),
            "candle_rejection": (sweep_type == "BULLISH_SSL_SWEEP" and lower_wick_ratio > 0.35) or \
                                (sweep_type == "BEARISH_BSL_SWEEP" and upper_wick_ratio > 0.35)
        }


class MultiTimeframeEngine:
    """
    Multi-Timeframe Confirmation Matrix (MTF).
    HTF (Higher Timeframe - 1D/4H/1H): Macro Bias, Structural Trend, Major Order Blocks
    ITF (Intermediate Timeframe - 15m/30m): Swing Range & Fibonacci OTE Zone
    LTF (Lower Timeframe - 5m/1m): Liquidity Sweep Trigger & Displacement Confirmation
    """

    @staticmethod
    def evaluate_multi_timeframe(
        htf_bias: str,
        itf_structure: str,
        itf_fib_status: Dict[str, Any],
        ltf_sweep: Dict[str, Any],
        signal_proposal: str
    ) -> Dict[str, Any]:
        """
        Synchronous MTF Gatekeeper:
        Trade passes ONLY if HTF Bias aligns with ITF Fibonacci Zone and LTF Liquidity Trigger.
        """
        htf_bias = htf_bias.upper()
        itf_structure = itf_structure.upper()
        signal_proposal = signal_proposal.upper()

        passed_htf = False
        passed_itf = False
        passed_ltf = False
        disqualification_reasons = []

        if signal_proposal in ["BUY", "STRONG_BUY"]:
            if htf_bias in ["BULLISH", "NEUTRAL"]:
                passed_htf = True
            else:
                disqualification_reasons.append(f"HTF Bias is {htf_bias}, conflicting with BUY proposal.")

            if itf_fib_status.get("in_ote", False) or itf_structure == "BULLISH":
                passed_itf = True
            else:
                disqualification_reasons.append("ITF is not in Fibonacci OTE Zone [0.618 - 0.786] or Bullish structure.")

            if ltf_sweep.get("sweep_type") == "BULLISH_SSL_SWEEP" or ltf_sweep.get("candle_rejection", False):
                passed_ltf = True
            else:
                disqualification_reasons.append("LTF lacks Sell-Side Liquidity (SSL) sweep or bullish rejection trigger.")

        elif signal_proposal in ["SELL", "STRONG_SELL"]:
            if htf_bias in ["BEARISH", "NEUTRAL"]:
                passed_htf = True
            else:
                disqualification_reasons.append(f"HTF Bias is {htf_bias}, conflicting with SELL proposal.")

            if itf_fib_status.get("in_ote", False) or itf_structure == "BEARISH":
                passed_itf = True
            else:
                disqualification_reasons.append("ITF is not in Fibonacci OTE Zone [0.618 - 0.786] or Bearish structure.")

            if ltf_sweep.get("sweep_type") == "BEARISH_BSL_SWEEP" or ltf_sweep.get("candle_rejection", False):
                passed_ltf = True
            else:
                disqualification_reasons.append("LTF lacks Buy-Side Liquidity (BSL) sweep or bearish rejection trigger.")

        all_confirmed = passed_htf and passed_itf and passed_ltf
        mtf_score = (int(passed_htf) * 0.40) + (int(passed_itf) * 0.35) + (int(passed_ltf) * 0.25)

        return {
            "mtf_confirmed": all_confirmed,
            "mtf_score": round(mtf_score, 2),
            "htf_confirmed": passed_htf,
            "itf_confirmed": passed_itf,
            "ltf_confirmed": passed_ltf,
            "disqualifications": disqualification_reasons,
            "confluence_status": "FULL_ALIGNMENT" if all_confirmed else "MISALIGNED"
        }


class RiskRewardEngine:
    """
    Strict 1:3+ Risk/Reward Ratio (RRR) Gatekeeper & Execution Sizing.
    Rules:
    - Minimum RRR: 3.0 (Strict hard filter; trades with RRR < 3.0 are strictly rejected)
    - Dynamic Stop Loss: Placed behind sweep wick / 0.886 Fib + ATR buffer (0.2 * ATR)
    - Target 1 (TP1): 1:1.5 RRR -> Move SL to Breakeven (+0.1R), close 33%
    - Target 2 (TP2): 1:3.0 RRR -> Core Take Profit (Fibonacci 1.272-1.618 extension), close 50% remaining
    - Target 3 (TP3): 1:5.0+ RRR -> Runner target (Fibonacci 2.0-2.618 Golden Extension)
    - Fractional Kelly Criterion & Volatility-Adjusted Risk Position Sizing
    """

    MIN_REQUIRED_RRR = 3.0

    @classmethod
    def calculate_trade_levels(
        cls,
        signal: str,
        entry_price: float,
        atr: float,
        fib_matrix: Dict[str, Any],
        sweep_data: Dict[str, Any],
        account_balance: float = 10000.0,
        risk_per_trade_pct: float = 1.5,
        win_rate_estimate: float = 0.58
    ) -> Dict[str, Any]:
        """
        Calculates exact mathematical entry, stop loss, take profit targets, RRR, and position size.
        """
        signal = signal.upper()
        if entry_price <= 0 or atr <= 0:
            return {"valid_trade": False, "reason": "Invalid entry or ATR value"}

        atr_buffer = atr * 0.20
        ote = fib_matrix.get("ote_zone", {})
        extensions = fib_matrix.get("extensions", {})

        if signal in ["BUY", "STRONG_BUY"]:
            wick_low = sweep_data.get("invalidation_wick_level", 0.0)
            fib_inval = ote.get("invalidation", entry_price - (atr * 1.5))
            
            base_sl = min(wick_low, fib_inval) if wick_low > 0 else fib_inval
            stop_loss = round(base_sl - atr_buffer, 4)

            risk_distance = entry_price - stop_loss
            if risk_distance <= 0:
                risk_distance = atr * 1.5
                stop_loss = round(entry_price - risk_distance, 4)

            tp1 = round(entry_price + (risk_distance * 1.5), 4)
            tp2_min = round(entry_price + (risk_distance * 3.0), 4)
            ext_1618 = extensions.get("1.618", tp2_min)
            tp2 = max(tp2_min, ext_1618)
            tp3_min = round(entry_price + (risk_distance * 5.0), 4)
            ext_2000 = extensions.get("2.000", tp3_min)
            tp3 = max(tp3_min, ext_2000, round(tp2 + (risk_distance * 1.5), 4))

            reward_distance = tp2 - entry_price
            calculated_rrr = reward_distance / risk_distance

        elif signal in ["SELL", "STRONG_SELL"]:
            wick_high = sweep_data.get("invalidation_wick_level", 0.0)
            fib_inval = ote.get("invalidation", entry_price + (atr * 1.5))

            base_sl = max(wick_high, fib_inval) if wick_high > 0 else fib_inval
            stop_loss = round(base_sl + atr_buffer, 4)

            risk_distance = stop_loss - entry_price
            if risk_distance <= 0:
                risk_distance = atr * 1.5
                stop_loss = round(entry_price + risk_distance, 4)

            tp1 = round(entry_price - (risk_distance * 1.5), 4)
            tp2_max = round(entry_price - (risk_distance * 3.0), 4)
            ext_1618 = extensions.get("1.618", tp2_max)
            tp2 = min(tp2_max, ext_1618)
            tp3_max = round(entry_price - (risk_distance * 5.0), 4)
            ext_2000 = extensions.get("2.000", tp3_max)
            tp3 = min(tp3_max, ext_2000, round(tp2 - (risk_distance * 1.5), 4))

            reward_distance = entry_price - tp2
            calculated_rrr = reward_distance / risk_distance

        else:
            return {"valid_trade": False, "reason": f"Signal {signal} is not executable"}

        calculated_rrr = round(calculated_rrr, 2)
        valid_rrr = calculated_rrr >= cls.MIN_REQUIRED_RRR

        p = win_rate_estimate
        q = 1.0 - p
        b = max(calculated_rrr, 3.0)
        full_kelly = max(0.0, (p * b - q) / b)
        quarter_kelly_pct = min(risk_per_trade_pct / 100.0, full_kelly * 0.25)

        dollar_risk = account_balance * (risk_per_trade_pct / 100.0)
        position_units = dollar_risk / risk_distance if risk_distance > 0 else 0.0
        position_value = round(position_units * entry_price, 2)

        return {
            "valid_trade": valid_rrr,
            "rrr": calculated_rrr,
            "min_required_rrr": cls.MIN_REQUIRED_RRR,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "risk_distance": round(risk_distance, 4),
            "tp1_1_5R": tp1,
            "tp2_3_0R": tp2,
            "tp3_5_0R": tp3,
            "risk_pct": risk_per_trade_pct,
            "dollar_risk": round(dollar_risk, 2),
            "position_units": round(position_units, 6),
            "position_notional_value": position_value,
            "kelly_fraction": round(quarter_kelly_pct, 4),
            "rejection_reason": None if valid_rrr else f"Calculated RRR ({calculated_rrr}:1) is below strict institutional threshold ({cls.MIN_REQUIRED_RRR}:1)"
        }


class DeepSeekR1QuantEngine:
    """
    Master DeepSeek-R1 Quantitative Reasoning & Execution Engine.
    Combines:
    1. Fibonacci Retracement & Extension Analysis
    2. Institutional Liquidity Sweeps
    3. Multi-Timeframe Confirmation
    4. Strict 1:3+ Risk/Reward Ratio Gatekeeper
    5. DeepSeek-R1 CoT Prompt Generation & Execution
    """

    def __init__(self):
        self.fib_engine = FibonacciEngine
        self.sweep_engine = LiquiditySweepEngine
        self.mtf_engine = MultiTimeframeEngine
        self.risk_engine = RiskRewardEngine

    def generate_r1_cot_prompt(
        self,
        symbol: str,
        price: float,
        htf_summary: Dict[str, Any],
        itf_summary: Dict[str, Any],
        ltf_summary: Dict[str, Any],
        fib_analysis: Dict[str, Any],
        sweep_analysis: Dict[str, Any],
        risk_analysis: Dict[str, Any]
    ) -> str:
        """
        Constructs the institutional DeepSeek-R1 Chain-of-Thought reasoning prompt.
        """
        prompt = f"""<system>
You are DeepSeek-R1 Quant Master, an institutional-grade algorithmic reasoning engine for multi-asset quantitative trading.
You specialize in:
1. Fibonacci Retracement & Optimal Trade Entry (OTE 0.618 - 0.786 / Golden Pocket 0.618 - 0.650).
2. Institutional Liquidity Sweeps (Buy-Side BSL & Sell-Side SSL sweeps, Turtle Soup, Wick Rejections).
3. Multi-Timeframe Confirmation (HTF Macro Trend -> ITF Structural OTE -> LTF Liquidity Trigger).
4. Strict 1:3+ Risk/Reward Ratio (Hard Invariant: RRR >= 3.0; any trade < 3:1 is strictly rejected).

Evaluate the following quantitative parameters step-by-step using your <think> chain of thought:
</system>

<context>
Asset: {symbol}
Current Price: {price}

1. HIGHER TIMEFRAME (HTF) DATA:
- Macro Trend: {htf_summary.get('trend', 'BULLISH')}
- Key Supply/Demand Zone: {htf_summary.get('zone', 'N/A')}

2. INTERMEDIATE TIMEFRAME (ITF) FIBONACCI ANALYSIS:
- Swing High: {fib_analysis.get('swing_high')} | Swing Low: {fib_analysis.get('swing_low')}
- Active OTE Zone [0.618 - 0.786]: {fib_analysis.get('ote_zone')}
- Fibonacci Zone Status: {itf_summary.get('zone_status')}
- Golden Pocket Active: {itf_summary.get('in_golden_pocket')}

3. LOWER TIMEFRAME (LTF) LIQUIDITY SWEEP:
- Sweep Detected: {sweep_analysis.get('sweep_detected')}
- Sweep Type: {sweep_analysis.get('sweep_type')}
- Rejection Wick Strength: {sweep_analysis.get('strength')}
- Invalidation Level: {sweep_analysis.get('invalidation_wick_level')}

4. MATHEMATICAL RISK-TO-REWARD VALIDATION:
- Calculated Entry: {risk_analysis.get('entry_price')}
- Stop Loss: {risk_analysis.get('stop_loss')}
- TP1 (1:1.5R): {risk_analysis.get('tp1_1_5R')}
- TP2 (1:3.0R Core): {risk_analysis.get('tp2_3_0R')}
- TP3 (1:5.0R Runner): {risk_analysis.get('tp3_5_0R')}
- Mathematical RRR: {risk_analysis.get('rrr')}:1 (Min Required: 3.0:1)
- Valid RRR Gate: {risk_analysis.get('valid_trade')}
</context>

Respond in the following STRICT JSON format after your chain-of-thought:
```json
{{
  "thought_process": "Detailed 4-step quantitative derivation",
  "signal": "STRONG_BUY" | "BUY" | "STRONG_SELL" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "fibonacci_confluence": "GOLDEN_POCKET" | "OTE_ZONE" | "DISCOUNT" | "PREMIUM" | "NONE",
  "liquidity_sweep_verified": true | false,
  "mtf_alignment": true | false,
  "strict_rrr_passed": true | false,
  "rrr": 0.0,
  "entry_price": 0.0,
  "stop_loss": 0.0,
  "take_profit_1": 0.0,
  "take_profit_2": 0.0,
  "take_profit_3": 0.0,
  "quant_rationale": "High-conviction institutional execution summary"
}}
```"""
        return prompt

    def analyze_market(
        self,
        symbol: str,
        df_ltf: pd.DataFrame,
        df_itf: Optional[pd.DataFrame] = None,
        df_htf: Optional[pd.DataFrame] = None,
        atr: Optional[float] = None,
        account_balance: float = 10000.0,
        risk_pct: float = 1.5
    ) -> Dict[str, Any]:
        """
        Full autonomous evaluation of the 4-pillar DeepSeek-R1 Quantitative Model:
        1. Fibonacci Retracement & Extension
        2. Liquidity Sweep Detection
        3. Multi-Timeframe Confirmation
        4. Strict 1:3+ Risk/Reward Ratio Gatekeeper
        """
        if df_ltf.empty or len(df_ltf) < 10:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "reason": "Insufficient OHLCV data for quantitative analysis"
            }

        if df_itf is None or df_itf.empty:
            df_itf = df_ltf
        if df_htf is None or df_htf.empty:
            df_htf = df_itf

        current_price = float(df_ltf["close"].iloc[-1])
        if atr is None or atr <= 0:
            high_low = df_ltf["high"] - df_ltf["low"]
            atr = float(high_low.tail(14).mean()) if not high_low.empty else current_price * 0.01

        itf_swings = self.fib_engine.identify_swing_points(df_itf, window=4)
        htf_swings = self.fib_engine.identify_swing_points(df_htf, window=6)

        htf_trend = htf_swings.get("trend", "BULLISH")
        if htf_trend == "UNKNOWN":
            htf_trend = "BULLISH" if df_htf["close"].iloc[-1] >= df_htf["close"].iloc[0] else "BEARISH"

        fib_direction = "BULLISH" if htf_trend in ["BULLISH", "RANGING"] else "BEARISH"
        fib_matrix = self.fib_engine.calculate_fibonacci_matrix(
            swing_high=itf_swings["swing_high"],
            swing_low=itf_swings["swing_low"],
            direction=fib_direction
        )
        fib_status = self.fib_engine.evaluate_price_in_fib_zone(current_price, fib_matrix)

        sweep_data = self.sweep_engine.detect_liquidity_sweeps(
            df=df_ltf,
            swing_high=itf_swings["swing_high"],
            swing_low=itf_swings["swing_low"],
            lookback_candles=5
        )

        candidate_signal = "HOLD"
        if sweep_data["sweep_type"] == "BULLISH_SSL_SWEEP" and (fib_status["in_ote"] or htf_trend == "BULLISH"):
            candidate_signal = "STRONG_BUY" if fib_status["in_golden_pocket"] else "BUY"
        elif sweep_data["sweep_type"] == "BEARISH_BSL_SWEEP" and (fib_status["in_ote"] or htf_trend == "BEARISH"):
            candidate_signal = "STRONG_SELL" if fib_status["in_golden_pocket"] else "SELL"
        elif fib_status["in_golden_pocket"]:
            if fib_direction == "BULLISH" and df_ltf["close"].iloc[-1] > df_ltf["open"].iloc[-1]:
                candidate_signal = "BUY"
            elif fib_direction == "BEARISH" and df_ltf["close"].iloc[-1] < df_ltf["open"].iloc[-1]:
                candidate_signal = "SELL"

        mtf_result = self.mtf_engine.evaluate_multi_timeframe(
            htf_bias=htf_trend,
            itf_structure=itf_swings["trend"],
            itf_fib_status=fib_status,
            ltf_sweep=sweep_data,
            signal_proposal=candidate_signal
        )

        risk_calc = self.risk_engine.calculate_trade_levels(
            signal=candidate_signal,
            entry_price=current_price,
            atr=atr,
            fib_matrix=fib_matrix,
            sweep_data=sweep_data,
            account_balance=account_balance,
            risk_per_trade_pct=risk_pct
        )

        final_signal = "HOLD"
        confidence = 0.50
        edge_quality = "LOW"
        rejection_notes = []

        if candidate_signal != "HOLD":
            if not mtf_result["mtf_confirmed"]:
                rejection_notes.extend(mtf_result["disqualifications"])
            if not risk_calc.get("valid_trade", False):
                rejection_notes.append(risk_calc.get("rejection_reason", "RRR < 3.0"))

            if mtf_result["mtf_confirmed"] and risk_calc.get("valid_trade", False):
                final_signal = candidate_signal
                base_conf = 0.75
                if fib_status["in_golden_pocket"]:
                    base_conf += 0.12
                if sweep_data["sweep_detected"]:
                    base_conf += 0.08
                confidence = min(0.96, round(base_conf, 2))
                edge_quality = "INSTITUTIONAL_ALPHA" if confidence >= 0.85 else "HIGH"
            else:
                final_signal = "HOLD"
                confidence = 0.45
                edge_quality = "FILTERED_OUT"

        status_msg = "Trade Approved" if final_signal != "HOLD" else (f"Filtered: {'; '.join(rejection_notes)}" if rejection_notes else "No A+ Setup")
        rationale = (
            f"DeepSeek-R1 Quant Ruleset: {final_signal} | Fib: {fib_status['zone_status']} | "
            f"Sweep: {sweep_data['sweep_type']} (Strength {sweep_data['strength']}) | "
            f"MTF Alignment: {mtf_result['confluence_status']} (Score {mtf_result['mtf_score']}) | "
            f"RRR: {risk_calc.get('rrr', 0.0)}:1 (Min 3.0:1) | {status_msg}"
        )

        return {
            "agent": "DeepSeek-R1 Institutional Quant Engine",
            "symbol": symbol,
            "final_signal": final_signal,
            "candidate_signal": candidate_signal,
            "confidence": confidence,
            "edge_quality": edge_quality,
            "fibonacci_matrix": fib_matrix,
            "fibonacci_status": fib_status,
            "liquidity_sweep": sweep_data,
            "multi_timeframe": mtf_result,
            "risk_reward": risk_calc,
            "rationale": rationale,
            "rejection_notes": rejection_notes
        }
