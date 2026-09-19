"""
Test Suite for DeepSeek-R1 Quantitative Trading Ruleset Engine
=============================================================
Tests:
1. Fibonacci Retracement & Extension calculations (Golden Pocket 0.618 - 0.650, OTE 0.618 - 0.786).
2. Liquidity Sweeps & Wick Rejection detection (BSL / SSL Turtle Soup).
3. Multi-Timeframe Confirmation Gatekeeper (HTF, ITF, LTF Alignment).
4. Strict 1:3+ Risk/Reward Ratio Invariant Enforcement & Kelly Position Sizing.
5. End-to-End Market Execution & DeepSeek-R1 CoT Prompt Generation.
"""

import unittest
import pandas as pd
import numpy as np
from strategies.deepseek_r1_ruleset import (
    FibonacciEngine,
    LiquiditySweepEngine,
    MultiTimeframeEngine,
    RiskRewardEngine,
    DeepSeekR1QuantEngine
)
from ai_swarm.deepseek_quant_agent import DeepSeekQuantAgent

class TestDeepSeekR1Ruleset(unittest.TestCase):

    def setUp(self):
        # Generate synthetic OHLCV data for testing
        np.random.seed(42)
        n = 50
        base_price = 100.0
        
        # Create an upward trend followed by a retracement into Golden Pocket
        prices = [base_price]
        for i in range(1, n):
            if i < 30:
                # Uptrend to ~120
                prices.append(prices[-1] + np.random.uniform(0.2, 1.2))
            else:
                # Retracement back down towards 107 (Golden Pocket ~0.618)
                prices.append(prices[-1] - np.random.uniform(0.3, 1.0))

        df_data = []
        for i, p in enumerate(prices):
            o = p - np.random.uniform(-0.3, 0.3)
            h = max(o, p) + np.random.uniform(0.2, 0.8)
            l = min(o, p) - np.random.uniform(0.2, 0.8)
            c = p
            df_data.append({"open": o, "high": h, "low": l, "close": c, "volume": 1000 + i * 10})

        self.df_uptrend = pd.DataFrame(df_data)

    def test_fibonacci_matrix_calculations(self):
        """Test exact mathematical Fibonacci retracements and extensions."""
        swing_high = 120.0
        swing_low = 100.0
        diff = 20.0

        # Bullish Retracements
        matrix = FibonacciEngine.calculate_fibonacci_matrix(swing_high, swing_low, direction="BULLISH")
        self.assertEqual(matrix["direction"], "BULLISH")
        self.assertEqual(matrix["delta"], 20.0)

        retracements = matrix["retracements"]
        self.assertAlmostEqual(retracements["0.000"], 120.0)
        self.assertAlmostEqual(retracements["0.500"], 110.0)
        self.assertAlmostEqual(retracements["0.618"], 120.0 - (20.0 * 0.618))
        self.assertAlmostEqual(retracements["0.650"], 120.0 - (20.0 * 0.650))
        self.assertAlmostEqual(retracements["0.786"], 120.0 - (20.0 * 0.786))
        self.assertAlmostEqual(retracements["0.886"], 120.0 - (20.0 * 0.886))

        # Golden Pocket Bounds
        ote = matrix["ote_zone"]
        self.assertAlmostEqual(ote["ote_top"], 120.0 - (20.0 * 0.618))
        self.assertAlmostEqual(ote["ote_pocket"], 120.0 - (20.0 * 0.650))
        self.assertAlmostEqual(ote["ote_bottom"], 120.0 - (20.0 * 0.786))

        # Extensions
        ext = matrix["extensions"]
        self.assertAlmostEqual(ext["1.618"], 100.0 + (20.0 * 1.618))

    def test_fibonacci_zone_evaluation(self):
        """Test detection of Golden Pocket [0.618 - 0.650] and OTE [0.618 - 0.786]."""
        swing_high = 120.0
        swing_low = 100.0
        matrix = FibonacciEngine.calculate_fibonacci_matrix(swing_high, swing_low, direction="BULLISH")

        # Price inside Golden Pocket: 120 - (20 * 0.63) = 107.4
        res_gp = FibonacciEngine.evaluate_price_in_fib_zone(107.4, matrix)
        self.assertTrue(res_gp["in_ote"])
        self.assertTrue(res_gp["in_golden_pocket"])
        self.assertEqual(res_gp["zone_status"], "GOLDEN_POCKET_0.618_0.650")

        # Price beyond invalidation (below 0.886: 120 - (20 * 0.886) = 102.28 -> 101.0)
        res_inval = FibonacciEngine.evaluate_price_in_fib_zone(101.0, matrix)
        self.assertFalse(res_inval["in_ote"])
        self.assertEqual(res_inval["zone_status"], "INVALIDATED_BELOW_0.886")

    def test_liquidity_sweep_detection(self):
        """Test Sell-Side Liquidity (SSL) and Buy-Side Liquidity (BSL) sweeps."""
        # Create a candle that wicks below swing_low but closes above it (Bullish SSL Sweep)
        swing_high = 120.0
        swing_low = 100.0

        candles = [
            {"open": 105.0, "high": 106.0, "low": 104.0, "close": 105.0},
            {"open": 105.0, "high": 105.5, "low": 103.0, "close": 103.5},
            {"open": 103.5, "high": 104.0, "low": 101.0, "close": 102.0},
            {"open": 102.0, "high": 103.0, "low": 98.5, "close": 101.5} # Low 98.5 < 100, Close 101.5 > 100
        ]
        df = pd.DataFrame(candles)

        sweep = LiquiditySweepEngine.detect_liquidity_sweeps(df, swing_high, swing_low)
        self.assertTrue(sweep["sweep_detected"])
        self.assertEqual(sweep["sweep_type"], "BULLISH_SSL_SWEEP")
        self.assertEqual(sweep["invalidation_wick_level"], 98.5)
        self.assertGreaterEqual(sweep["strength"], 0.65)

    def test_multi_timeframe_confirmation(self):
        """Test synchronous MTF gatekeeper logic."""
        # 1. Aligned Bullish Setup
        res_pass = MultiTimeframeEngine.evaluate_multi_timeframe(
            htf_bias="BULLISH",
            itf_structure="BULLISH",
            itf_fib_status={"in_ote": True},
            ltf_sweep={"sweep_type": "BULLISH_SSL_SWEEP", "candle_rejection": True},
            signal_proposal="BUY"
        )
        self.assertTrue(res_pass["mtf_confirmed"])
        self.assertEqual(res_pass["confluence_status"], "FULL_ALIGNMENT")
        self.assertEqual(len(res_pass["disqualifications"]), 0)

        # 2. Conflicting Setup (HTF Bearish while attempting BUY)
        res_fail = MultiTimeframeEngine.evaluate_multi_timeframe(
            htf_bias="BEARISH",
            itf_structure="BULLISH",
            itf_fib_status={"in_ote": True},
            ltf_sweep={"sweep_type": "BULLISH_SSL_SWEEP", "candle_rejection": True},
            signal_proposal="BUY"
        )
        self.assertFalse(res_fail["mtf_confirmed"])
        self.assertEqual(res_fail["confluence_status"], "MISALIGNED")
        self.assertIn("HTF Bias is BEARISH", res_fail["disqualifications"][0])

    def test_strict_risk_reward_invariant(self):
        """Test that only trades with RRR >= 3.0 are approved and position sizing is accurate."""
        fib_matrix = FibonacciEngine.calculate_fibonacci_matrix(120.0, 100.0, "BULLISH")
        sweep_data = {"invalidation_wick_level": 105.0}
        entry = 107.0
        atr = 1.0

        risk_eval = RiskRewardEngine.calculate_trade_levels(
            signal="BUY",
            entry_price=entry,
            atr=atr,
            fib_matrix=fib_matrix,
            sweep_data=sweep_data,
            account_balance=10000.0,
            risk_per_trade_pct=1.5
        )

        self.assertTrue(risk_eval["valid_trade"])
        self.assertGreaterEqual(risk_eval["rrr"], 3.0)
        self.assertIsNotNone(risk_eval["stop_loss"])
        self.assertGreater(risk_eval["tp1_1_5R"], entry)
        self.assertGreater(risk_eval["tp2_3_0R"], risk_eval["tp1_1_5R"])
        self.assertGreater(risk_eval["tp3_5_0R"], risk_eval["tp2_3_0R"])
        self.assertEqual(risk_eval["dollar_risk"], 150.0) # 1.5% of 10000

    def test_end_to_end_quant_engine(self):
        """Test full DeepSeek-R1 Quantitative Engine analysis cycle."""
        engine = DeepSeekR1QuantEngine()
        result = engine.analyze_market(
            symbol="BTC/USDT",
            df_ltf=self.df_uptrend,
            account_balance=10000.0,
            risk_pct=1.5
        )

        self.assertIn("final_signal", result)
        self.assertIn("confidence", result)
        self.assertIn("fibonacci_matrix", result)
        self.assertIn("risk_reward", result)
        self.assertIn("rationale", result)

    def test_deepseek_quant_agent_integration(self):
        """Test integration of DeepSeekQuantAgent with deterministic ruleset fallback."""
        agent = DeepSeekQuantAgent()
        tech_summary = {"close": 107.4, "atr": 1.2, "bb_pct": 0.45}
        ml_summary = {"prediction": "BULLISH", "confidence": 0.78, "bullish_prob": 0.82}
        smc_summary = {"market_structure": "BULLISH_TREND", "liquidity_sweep": "BULLISH_SELL_SIDE_LIQUIDITY_SWEEP"}

        res = agent.analyze(
            symbol="ETH/USDT",
            tech_summary=tech_summary,
            ml_summary=ml_summary,
            df=self.df_uptrend,
            smc_summary=smc_summary
        )

        self.assertIn(res["signal"], ["BUY", "STRONG_BUY", "HOLD"])
        self.assertGreaterEqual(res["confidence"], 0.40)
        self.assertIn("rrr", res)

if __name__ == "__main__":
    unittest.main()
