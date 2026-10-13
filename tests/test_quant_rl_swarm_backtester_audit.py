"""
Comprehensive Deep Audit & Verification Suite for:
1. Quantitative Strategies (`strategies/`)
2. Reinforcement Learning Engine (`rl_engine/`)
3. AI Swarm & Consensus Matrix (`ai_swarm/`)
4. Institutional Backtester (`backtester/`)

Tests every single class and primary method across realistic 120-bar OHLCV data,
small (5-bar / 1-bar) DataFrames, empty DataFrames, missing timestamp columns,
flat-price DataFrames, and NaN-injected DataFrames with strict zero-warning enforcement.
"""

import os
import sys
import math
import tempfile
import warnings
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from strategies import (
    TechnicalIndicators,
    SmartMoneyConcepts,
    MLAlphaPredictor,
    StrategyOrchestrator,
    SuperTrendStrategy,
    SupertrendStrategy,
    FVGHunterStrategy,
    SMCOrderBlockStrategy,
    FibonacciEngine,
    LiquiditySweepEngine,
    MultiTimeframeEngine,
    RiskRewardEngine,
    DeepSeekR1QuantEngine,
)
from rl_engine import (
    TradingEnvironment,
    ActorCriticNN,
    PPOTradingAgent,
    PPOAgent,
    DQNAgent,
)
from ai_swarm import (
    QwenTechnicalAgent,
    DeepSeekQuantAgent,
    KimiMacroAgent,
    HFSentimentAgent,
    GroqSentimentAgent,
    AIConsensusMatrix,
    DeepThinkingVisionEngine,
    FineTuningEngine,
    fine_tuning_engine,
    MetaLearningOptimizer,
)
from backtester import (
    BacktestEngine,
    PerformanceMetrics,
    MonteCarloSimulator,
    PerformanceReportExporter,
)


def make_realistic_ohlcv(n: int = 120, seed: int = 42, include_timestamp: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = 65000.0
    rets = rng.normal(0.0005, 0.008, size=n)
    closes = base * np.cumprod(1.0 + rets)
    opens = np.roll(closes, 1)
    opens[0] = base
    spread = np.abs(rng.normal(0.004, 0.002, size=n)) * closes
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    volumes = rng.uniform(50.0, 500.0, size=n)

    data = {
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }
    if include_timestamp:
        data["timestamp"] = pd.date_range("2026-01-01", periods=n, freq="15min").astype(str)
    return pd.DataFrame(data)


def make_nan_ohlcv(n: int = 60) -> pd.DataFrame:
    df = make_realistic_ohlcv(n=n)
    df.loc[5, "close"] = np.nan
    df.loc[10, "high"] = np.nan
    df.loc[15, "low"] = np.nan
    df.loc[20, "open"] = np.nan
    df.loc[25, "volume"] = np.nan
    return df


def make_flat_ohlcv(n: int = 60) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min").astype(str),
        "open": np.full(n, 50000.0),
        "high": np.full(n, 50000.0),
        "low": np.full(n, 50000.0),
        "close": np.full(n, 50000.0),
        "volume": np.full(n, 100.0),
    })


def assert_no_nan_in_dict(d: dict, context: str = ""):
    for k, v in d.items():
        if isinstance(v, float):
            assert not math.isnan(v) and not math.isinf(v), f"NaN/Inf found in {context}[{k!r}] = {v}"
        elif isinstance(v, dict):
            assert_no_nan_in_dict(v, context=f"{context}.{k}")


def test_all_strategies_comprehensive():
    df_120 = make_realistic_ohlcv(120)
    df_no_ts = make_realistic_ohlcv(40, include_timestamp=False)
    df_small = make_realistic_ohlcv(5)
    df_one = make_realistic_ohlcv(1)
    df_empty = pd.DataFrame()
    df_nan = make_nan_ohlcv(65)
    df_flat = make_flat_ohlcv(65)

    datasets = [
        ("realistic_120", df_120),
        ("no_timestamp_40", df_no_ts),
        ("small_5", df_small),
        ("single_1", df_one),
        ("empty_0", df_empty),
        ("nan_65", df_nan),
        ("flat_65", df_flat),
    ]

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")

        # 1. TechnicalIndicators
        ti = TechnicalIndicators()
        for name, d in datasets:
            comp = ti.compute_all(d)
            assert isinstance(comp, pd.DataFrame), f"compute_all failed on {name}"
            summary = ti.get_latest_summary(d)
            assert isinstance(summary, dict), f"get_latest_summary failed on {name}"
            assert_no_nan_in_dict(summary, f"TechnicalIndicators.summary({name})")
            for m_name in ("generate_signal", "calculate_signals", "get_signal", "evaluate"):
                res = getattr(ti, m_name)(d)
                assert isinstance(res, dict) and "signal" in res and "confidence" in res
                assert_no_nan_in_dict(res, f"TechnicalIndicators.{m_name}({name})")

        # 2. SuperTrendStrategy / SupertrendStrategy
        st = SuperTrendStrategy(period=10, multiplier=3.0)
        st_alias = SupertrendStrategy(period=10, multiplier=3.0)
        assert isinstance(st_alias, SuperTrendStrategy)
        for name, d in datasets:
            for m_name in ("generate_signal", "calculate_signals", "get_signal", "evaluate", "predict"):
                res = getattr(st, m_name)(d)
                assert isinstance(res, dict) and res["signal"] in ("BUY", "SELL", "HOLD")
                assert_no_nan_in_dict(res, f"SuperTrendStrategy.{m_name}({name})")

        # 3. FVGHunterStrategy
        fvg = FVGHunterStrategy(min_gap_pct=0.05)
        for name, d in datasets:
            for m_name in ("scan_fvg", "generate_signal", "calculate_signals", "get_signal", "evaluate", "predict"):
                res = getattr(fvg, m_name)(d)
                assert isinstance(res, dict) and "signal" in res and "fvg_detected" in res
                assert_no_nan_in_dict(res, f"FVGHunterStrategy.{m_name}({name})")

        # 4. SMCOrderBlockStrategy
        ob = SMCOrderBlockStrategy(lookback=25)
        for name, d in datasets:
            for m_name in ("detect_order_blocks", "generate_signal", "calculate_signals", "get_signal", "evaluate", "predict"):
                res = getattr(ob, m_name)(d)
                assert isinstance(res, dict) and "signal" in res and "bias" in res
                assert_no_nan_in_dict(res, f"SMCOrderBlockStrategy.{m_name}({name})")

        # 5. SmartMoneyConcepts
        smc = SmartMoneyConcepts()
        for name, d in datasets:
            assert isinstance(smc.detect_fvg(d), list)
            assert isinstance(smc.detect_market_structure(d), dict)
            assert isinstance(smc.detect_liquidity_sweeps(d), (str, type(None)))
            for m_name in ("get_smc_summary", "generate_signal", "calculate_signals", "get_signal", "evaluate", "predict"):
                res = getattr(smc, m_name)(d)
                assert isinstance(res, dict) and "signal" in res and "recent_swing_high" in res
                assert_no_nan_in_dict(res, f"SmartMoneyConcepts.{m_name}({name})")

        # 6. MLAlphaPredictor
        ml = MLAlphaPredictor()
        for name, d in datasets:
            for m_name in ("predict_next_candle", "predict", "generate_signal", "calculate_signals", "get_signal", "evaluate"):
                res = getattr(ml, m_name)(d)
                assert isinstance(res, dict) and "signal" in res and "prediction" in res and "confidence" in res
                assert_no_nan_in_dict(res, f"MLAlphaPredictor.{m_name}({name})")

        # 7. DeepSeek-R1 Ruleset Engines
        fib_eng = FibonacciEngine()
        sweep_eng = LiquiditySweepEngine()
        mtf_eng = MultiTimeframeEngine()
        rr_eng = RiskRewardEngine()
        ds_eng = DeepSeekR1QuantEngine()

        for name, d in datasets:
            fib_res = fib_eng.evaluate(d)
            assert isinstance(fib_res, dict) and "zone_status" in fib_res
            assert_no_nan_in_dict(fib_res, f"FibonacciEngine({name})")

            sw_res = sweep_eng.evaluate(d)
            assert isinstance(sw_res, dict) and "strength" in sw_res and "signal" in sw_res
            assert_no_nan_in_dict(sw_res, f"LiquiditySweepEngine({name})")

            mtf_res = mtf_eng.evaluate(d)
            assert isinstance(mtf_res, dict) and "signal" in mtf_res
            assert_no_nan_in_dict(mtf_res, f"MultiTimeframeEngine({name})")

            for m_name in ("analyze_market", "evaluate", "generate_signal", "calculate_signals", "get_signal", "predict"):
                res = getattr(ds_eng, m_name)("BTC/USDT", d) if m_name == "analyze_market" else getattr(ds_eng, m_name)(d)
                assert isinstance(res, dict) and "signal" in res and "final_signal" in res
                assert_no_nan_in_dict(res, f"DeepSeekR1QuantEngine.{m_name}({name})")

        rr_res = rr_eng.evaluate("BUY", entry_price=65000.0, atr=500.0)
        assert isinstance(rr_res, dict) and rr_res["valid_trade"] is True
        assert_no_nan_in_dict(rr_res, "RiskRewardEngine")

        # 8. StrategyOrchestrator (mock network calls for deterministic instant execution)
        with patch("requests.post", side_effect= RuntimeError("offline_test_mode")), \
             patch("requests.get", side_effect=RuntimeError("offline_test_mode")):
            orch = StrategyOrchestrator()
            for name, d in datasets:
                for m_name in ("generate_signal", "calculate_signals", "get_signal", "evaluate", "predict", "run"):
                    res = getattr(orch, m_name)(d)
                    assert isinstance(res, dict) and "signal" in res and "final_action" in res
                    assert_no_nan_in_dict(res, f"StrategyOrchestrator.{m_name}({name})")

        runtime_warnings = [
            w for w in caught_warnings
            if issubclass(w.category, (RuntimeWarning, FutureWarning))
        ]
        assert len(runtime_warnings) == 0, f"Unexpected warnings in strategies: {[str(w.message) for w in runtime_warnings]}"


def test_all_rl_agents_comprehensive():
    df_120 = make_realistic_ohlcv(120)
    df_small = make_realistic_ohlcv(5)
    df_one = make_realistic_ohlcv(1)
    df_empty = pd.DataFrame()
    df_nan = make_nan_ohlcv(40)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")

        # 1. TradingEnvironment
        for name, d in [("120", df_120), ("5", df_small), ("1", df_one), ("empty", df_empty), ("nan", df_nan), ("none", None)]:
            env = TradingEnvironment(d)
            state = env.reset()
            assert isinstance(state, np.ndarray) and state.shape == (10,)
            assert not np.any(np.isnan(state)) and not np.any(np.isinf(state)), f"NaN in env.reset() for {name}"
            next_state, reward, done, info = env.step(1)
            assert isinstance(next_state, np.ndarray) and next_state.shape == (10,)
            assert not np.any(np.isnan(next_state))
            assert isinstance(reward, float) and not math.isnan(reward)
            assert isinstance(done, bool)
            eval_res = env.evaluate()
            assert isinstance(eval_res, dict) and "ending_balance" in eval_res

        # 2. ActorCriticNN & PPOTradingAgent / PPOAgent
        nn = ActorCriticNN(state_dim=10, hidden_dim=64, action_dim=3)
        probs, val = nn.forward(np.zeros(10))
        assert probs.shape == (3,) and abs(np.sum(probs) - 1.0) < 1e-5
        probs_nan, val_nan = nn.forward(np.array([np.nan, np.inf, -np.inf]))
        assert probs_nan.shape == (3,) and not np.any(np.isnan(probs_nan))

        ppo = PPOTradingAgent(state_dim=10, action_dim=3)
        ppo_alias = PPOAgent(state_dim=10, action_dim=3)
        assert isinstance(ppo_alias, PPOTradingAgent)

        for inp in [np.zeros(10), np.array([np.nan, 1.0]), df_120, df_small, df_empty, None]:
            act, prob, v = ppo.select_action(inp, training=False)
            assert act in (0, 1, 2) and not math.isnan(prob) and not math.isnan(v)
            for m_name in ("get_signal", "evaluate", "predict", "generate_signal", "calculate_signals", "act"):
                res = getattr(ppo, m_name)(inp)
                assert isinstance(res, dict) and res["signal"] in ("BUY", "SELL", "HOLD")
                assert_no_nan_in_dict(res, f"PPOTradingAgent.{m_name}")

        train_metrics = ppo.train_on_df(df_120, episodes=1)
        assert isinstance(train_metrics, dict) and "avg_reward" in train_metrics
        train_small = ppo.train_on_df(df_small, episodes=1)
        assert isinstance(train_small, dict)

        # 3. DQNAgent
        dqn = DQNAgent(state_dim=10, action_dim=3)
        for inp in [np.zeros(10), np.array([np.nan, 1.0]), df_120, df_small, df_empty, None]:
            a = dqn.act(inp)
            assert a in (0, 1, 2)
            for m_name in ("evaluate", "get_signal", "get_signal_and_confidence", "predict", "generate_signal", "calculate_signals"):
                res = getattr(dqn, m_name)(inp)
                assert isinstance(res, dict) and res["signal"] in ("BUY", "SELL", "HOLD")
                assert_no_nan_in_dict(res, f"DQNAgent.{m_name}")

        runtime_warnings = [
            w for w in caught_warnings
            if issubclass(w.category, (RuntimeWarning, FutureWarning))
        ]
        assert len(runtime_warnings) == 0, f"Unexpected warnings in rl_engine: {[str(w.message) for w in runtime_warnings]}"


def test_all_ai_swarm_modules_comprehensive():
    df_120 = make_realistic_ohlcv(120)
    df_small = make_realistic_ohlcv(5)
    df_empty = pd.DataFrame()
    df_nan = make_nan_ohlcv(40)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")

        with patch("requests.post", side_effect=RuntimeError("offline_test_mode")), \
             patch("requests.get", side_effect=RuntimeError("offline_test_mode")):

            qwen = QwenTechnicalAgent()
            deepseek = DeepSeekQuantAgent()
            kimi = KimiMacroAgent()
            hf = HFSentimentAgent()
            groq = GroqSentimentAgent()
            consensus = AIConsensusMatrix()
            vision = DeepThinkingVisionEngine()
            ft = FineTuningEngine(data_dir=tempfile.mkdtemp())
            meta = MetaLearningOptimizer()

            for agent in (qwen, deepseek, kimi, hf, groq):
                for m_name in ("analyze", "evaluate", "get_signal", "generate_signal", "calculate_signals", "predict", "run"):
                    res_default = getattr(agent, m_name)()
                    assert isinstance(res_default, dict) and res_default["signal"] in ("BUY", "SELL", "HOLD")
                    assert_no_nan_in_dict(res_default, f"{agent.__class__.__name__}.{m_name}(default)")

                    res_df = getattr(agent, m_name)(df_120)
                    assert isinstance(res_df, dict) and res_df["signal"] in ("BUY", "SELL", "HOLD")
                    assert_no_nan_in_dict(res_df, f"{agent.__class__.__name__}.{m_name}(df_120)")

                    res_empty = getattr(agent, m_name)(df_empty)
                    assert isinstance(res_empty, dict) and res_empty["signal"] in ("BUY", "SELL", "HOLD")
                    assert_no_nan_in_dict(res_empty, f"{agent.__class__.__name__}.{m_name}(df_empty)")

            # Test with NaN-polluted summaries
            nan_summary = {"close": float("nan"), "rsi": None, "macd_hist": float("nan"), "atr": 0.0, "bb_pct": None}
            for agent in (qwen, deepseek, kimi):
                res_nan = agent.analyze("BTC/USDT", nan_summary, nan_summary)
                assert isinstance(res_nan, dict) and res_nan["signal"] in ("BUY", "SELL", "HOLD")
                assert_no_nan_in_dict(res_nan, f"{agent.__class__.__name__}.analyze(nan_summary)")

            # AIConsensusMatrix
            for m_name in ("evaluate_market_consensus", "get_consensus", "evaluate", "generate_signal", "calculate_signals", "get_signal", "predict", "run"):
                res_c = getattr(consensus, m_name)()
                assert isinstance(res_c, dict) and "final_signal" in res_c and "signal" in res_c and "confidence" in res_c
                assert_no_nan_in_dict(res_c, f"AIConsensusMatrix.{m_name}(default)")

                res_c_df = getattr(consensus, m_name)(df_120)
                assert isinstance(res_c_df, dict) and "final_signal" in res_c_df and "signal" in res_c_df
                assert_no_nan_in_dict(res_c_df, f"AIConsensusMatrix.{m_name}(df_120)")

            # DeepThinkingVisionEngine
            for d in (df_120, df_small, df_empty, df_nan, None):
                for m_name in ("analyze_chart_geometry_vision", "evaluate", "generate_signal", "calculate_signals", "get_signal", "predict", "run"):
                    v_res = getattr(vision, m_name)(d)
                    assert isinstance(v_res, dict)
                    for req_key in ("primary_pattern", "primary_type", "confidence", "description", "all_detected_patterns", "detected_patterns", "signal"):
                        assert req_key in v_res, f"Missing {req_key} in DeepThinkingVisionEngine.{m_name}"
                    assert_no_nan_in_dict(v_res, f"DeepThinkingVisionEngine.{m_name}")

            cot_res = vision.generate_chain_of_thought_deep_thinking()
            assert isinstance(cot_res, dict) and "verdict" in cot_res and "signal" in cot_res
            assert_no_nan_in_dict(cot_res, "DeepThinkingVisionEngine.generate_chain_of_thought_deep_thinking")

            # FineTuningEngine & MetaLearningOptimizer
            for m_name in ("execute_fine_tuning_step", "get_tuning_status", "get_status", "evaluate", "run", "predict"):
                ft_res = getattr(ft, m_name)()
                assert isinstance(ft_res, dict) and "current_loss" in ft_res

            for m_name in ("optimize_from_trade_results", "get_summary", "evaluate", "run", "predict"):
                m_res = getattr(meta, m_name)()
                assert isinstance(m_res, dict) and "current_model_weights" in m_res

        runtime_warnings = [
            w for w in caught_warnings
            if issubclass(w.category, (RuntimeWarning, FutureWarning))
        ]
        assert len(runtime_warnings) == 0, f"Unexpected warnings in ai_swarm: {[str(w.message) for w in runtime_warnings]}"


def test_all_backtester_modules_comprehensive():
    df_120 = make_realistic_ohlcv(120)
    df_no_ts = make_realistic_ohlcv(50, include_timestamp=False)
    df_small = make_realistic_ohlcv(5)
    df_empty = pd.DataFrame()
    df_nan = make_nan_ohlcv(60)
    df_flat = make_flat_ohlcv(60)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")

        bt = BacktestEngine(initial_capital=10000.0)
        expected_keys = {
            "initial_capital", "ending_capital", "total_net_profit", "return_pct",
            "total_trades", "win_count", "loss_count", "win_rate_pct",
            "profit_factor", "avg_win", "avg_loss", "expectancy_per_trade",
            "sharpe_ratio", "sortino_ratio", "max_drawdown_pct", "equity_curve",
            "symbol", "bars_analyzed", "trades_list",
        }

        for name, d in [
            ("120", df_120),
            ("no_ts", df_no_ts),
            ("small_5", df_small),
            ("empty", df_empty),
            ("nan", df_nan),
            ("flat", df_flat),
            ("none", None),
        ]:
            for m_name in ("run", "evaluate", "run_simulation"):
                res = getattr(bt, m_name)(d, symbol="BTC/USDT")
                assert isinstance(res, dict), f"BacktestEngine.{m_name} failed on {name}"
                missing = expected_keys - set(res.keys())
                assert not missing, f"Missing keys {missing} in BacktestEngine.{m_name}({name})"
                assert_no_nan_in_dict(res, f"BacktestEngine.{m_name}({name})")

        # PerformanceMetrics
        pm_empty = PerformanceMetrics.calculate([])
        pm_non_empty = PerformanceMetrics.calculate([
            {"pnl": 120.0, "pnl_pct": 1.2},
            {"pnl": -45.0, "pnl_pct": -0.45},
            {"pnl": float("nan"), "pnl_pct": float("nan")},
        ])
        assert set(pm_empty.keys()) == set(pm_non_empty.keys()), "PerformanceMetrics keys mismatch between empty and non-empty"
        assert_no_nan_in_dict(pm_empty, "PerformanceMetrics(empty)")
        assert_no_nan_in_dict(pm_non_empty, "PerformanceMetrics(non_empty)")

        # MonteCarloSimulator
        for pnls in ([], [100.0, -50.0, float("nan"), None], [120.0, -40.0, 80.0, 200.0, -60.0, 150.0]):
            for m_name in ("run_simulation", "run", "evaluate"):
                mc_res = getattr(MonteCarloSimulator, m_name)(pnls, initial_capital=10000.0, num_simulations=100, trade_count=20)
                assert isinstance(mc_res, dict) and "probability_of_profit_pct" in mc_res and "cvar_99_pct" in mc_res
                assert_no_nan_in_dict(mc_res, f"MonteCarloSimulator.{m_name}")

        # PerformanceReportExporter
        tmpdir = tempfile.mkdtemp()
        csv_path = os.path.join(tmpdir, "trades.csv")
        json_path = os.path.join(tmpdir, "audit.json")
        assert PerformanceReportExporter.export_trade_history_csv([], csv_path) == ""
        out_csv = PerformanceReportExporter.export_trade_history_csv([{"symbol": "BTC/USDT", "pnl": 50.0}], csv_path)
        assert os.path.exists(out_csv)
        out_json = PerformanceReportExporter.export_quant_audit_json(
            {"equity": np.float64(10500.0)},
            pm_non_empty,
            json_path
        )
        assert os.path.exists(out_json)
        assert isinstance(PerformanceReportExporter.evaluate(), dict)
        assert isinstance(PerformanceReportExporter.run(), dict)

        runtime_warnings = [
            w for w in caught_warnings
            if issubclass(w.category, (RuntimeWarning, FutureWarning))
        ]
        assert len(runtime_warnings) == 0, f"Unexpected warnings in backtester: {[str(w.message) for w in runtime_warnings]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
