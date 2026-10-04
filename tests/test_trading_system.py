import sys
import os
import pandas as pd
import numpy as np

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from core.market_data import MarketDataProvider
from core.portfolio import Portfolio
from core.risk_engine import RiskEngine
from core.order_manager import OrderManager
from strategies.indicators import TechnicalIndicators
from strategies.smart_money_concepts import SmartMoneyConcepts
from strategies.ml_predictor import MLAlphaPredictor
from ai_swarm.consensus_matrix import AIConsensusMatrix
from backtester.engine import BacktestEngine
from backtester.monte_carlo import MonteCarloSimulator

def test_market_data_generation():
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv("BTC/USDT", timeframe="15m", limit=50)
    assert not df.empty
    assert len(df) == 50
    assert all(col in df.columns for col in ["timestamp", "open", "high", "low", "close", "volume"])
    assert df["close"].iloc[-1] > 0

def test_technical_indicators():
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv("BTC/USDT", limit=60)
    df_calc = TechnicalIndicators.compute_all(df)
    
    assert "rsi" in df_calc.columns
    assert "macd" in df_calc.columns
    assert "supertrend_dir" in df_calc.columns
    assert "bb_upper" in df_calc.columns
    assert "atr" in df_calc.columns

    summary = TechnicalIndicators.get_latest_summary(df)
    assert "rsi" in summary
    assert "supertrend_is_bull" in summary
    assert 0 <= summary["rsi"] <= 100

def test_smart_money_concepts():
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv("BTC/USDT", limit=80)
    smc = SmartMoneyConcepts.get_smc_summary(df)
    
    assert "market_structure" in smc
    assert "active_fvgs_count" in smc
    assert isinstance(smc["active_fvgs_count"], int)

def test_ml_predictor():
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv("BTC/USDT", limit=80)
    predictor = MLAlphaPredictor()
    pred = predictor.predict_next_candle(df)
    
    assert "prediction" in pred
    assert pred["prediction"] in ["BULLISH", "BEARISH", "NEUTRAL", "STRONG_BULLISH", "STRONG_BEARISH"]
    assert 0.0 <= pred["confidence"] <= 1.0

def test_ai_consensus():
    consensus = AIConsensusMatrix()
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv("BTC/USDT", limit=60)
    tech = TechnicalIndicators.get_latest_summary(df)
    smc = SmartMoneyConcepts.get_smc_summary(df)
    predictor = MLAlphaPredictor()
    ml = predictor.predict_next_candle(df)
    
    res = consensus.evaluate_market_consensus("BTC/USDT", tech, smc, ml)
    assert "final_signal" in res
    assert res["final_signal"] in ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
    assert len(res["swarm_deliberation"]) == 4

def test_risk_and_order_flow():
    import tempfile
    from pathlib import Path
    temp_storage = Path(tempfile.gettempdir()) / "test_portfolio_temp.json"
    if temp_storage.exists():
        try:
            temp_storage.unlink()
        except Exception:
            pass
    portfolio = Portfolio(initial_balance=10000.0, storage_path=temp_storage)
    portfolio.cash = 10000.0
    portfolio.equity = 10000.0
    portfolio.daily_start_equity = 10000.0
    portfolio.positions = {}
    risk_engine = RiskEngine(portfolio)
    risk_engine.is_circuit_broken = False
    order_manager = OrderManager(portfolio, risk_engine)
    order_manager.set_mode("paper")

    # Test position sizing
    size = risk_engine.calculate_position_size("BTC/USDT", entry_price=95000.0, stop_loss_price=93500.0)
    assert size > 0

    # Test SL and TP calculation
    sl, tps = risk_engine.calculate_sl_tp("BUY", entry_price=95000.0, atr=1000.0)
    assert sl < 95000.0
    assert len(tps) == 3
    assert tps[0] > 95000.0

    # Test Execution
    res = order_manager.execute_signal("BTC/USDT", "BUY", current_price=95000.0, atr=1000.0, reason="Test Execution")
    assert res["status"] in ["OPENED", "ALREADY_OPEN"]
    
    summary = portfolio.get_summary()
    assert summary["equity"] > 0

    # Test Close
    close_rec = order_manager.close_trade("BTC/USDT", current_price=96000.0, reason="TEST_CLOSE")
    if close_rec:
        assert close_rec["pnl"] > 0

    # 1. Verify Dynamic Slippage Calculation
    slip_pct_low, exec_p_low = order_manager.calculate_dynamic_slippage("BTC/USDT", current_price=95000.0, side="BUY", amount=0.01, atr=500.0)
    slip_pct_high, exec_p_high = order_manager.calculate_dynamic_slippage("BTC/USDT", current_price=95000.0, side="BUY", amount=2.0, atr=3000.0)
    assert slip_pct_high > slip_pct_low, "High ATR & large notional must produce higher dynamic slippage"
    assert exec_p_high > exec_p_low, "BUY execution price under high slippage must be higher"

    # 2. Verify Partial Fill Handler
    part_res1 = order_manager.handle_partial_fill(
        symbol="ETH/USDT",
        order_id="ORD_ETH_101",
        side="BUY",
        filled_amount=1.0,
        fill_price=2700.0,
        remaining_amount=1.0,
        sl_price=2600.0,
        tp_levels=[2800.0, 2900.0, 3050.0],
        reason="Initial partial fill"
    )
    assert "ETH/USDT" in portfolio.positions
    assert portfolio.positions["ETH/USDT"]["amount"] == 1.0

    # Incremental partial fill on same position
    part_res2 = order_manager.handle_partial_fill(
        symbol="ETH/USDT",
        order_id="ORD_ETH_101",
        side="BUY",
        filled_amount=1.0,
        fill_price=2720.0,
        remaining_amount=0.0,
        sl_price=2600.0,
        tp_levels=[2800.0, 2900.0, 3050.0],
        reason="Final fill completion"
    )
    assert portfolio.positions["ETH/USDT"]["amount"] == 2.0
    assert portfolio.positions["ETH/USDT"]["entry_price"] == 2710.0, "VWAP entry price must average 2700 and 2720"

    # 3. Verify Emergency Cancel-All Triggers
    cancel_report = order_manager.emergency_cancel_all(flatten_positions=True, current_prices={"ETH/USDT": 2750.0})
    assert cancel_report["status"] == "EMERGENCY_CANCEL_ALL_COMPLETED"
    assert cancel_report["circuit_breaker_active"] is True
    assert "ETH/USDT" not in portfolio.positions, "Emergency flatten must close active positions"
    assert risk_engine.is_circuit_broken is True

def test_mt5_execution_bridges():
    from core.mt5_engine import MT5InstitutionalEngine
    import tempfile
    mt5 = MT5InstitutionalEngine(data_dir=tempfile.gettempdir())

    # 1. Verify MT5 Dynamic Slippage
    slip_pips_small, exec_p_small, dev_small = mt5.calculate_dynamic_slippage("XAUUSD", "BUY", lots=0.10)
    slip_pips_large, exec_p_large, dev_large = mt5.calculate_dynamic_slippage("XAUUSD", "BUY", lots=15.0)
    assert slip_pips_large > slip_pips_small, "Large block lots must experience higher MT5 slippage"
    assert dev_large >= dev_small, "Deviation points must scale with order volume"

    # 2. Verify Order Execution with Dynamic Slippage & Deviation
    order_res = mt5.order_send(symbol="XAUUSD", action="BUY", lots=0.50, sl_pips=50.0, tp_pips=100.0)
    assert order_res["status"] == "SUCCESS"
    assert "slippage_pips" in order_res
    assert "deviation_points" in order_res
    ticket = order_res["ticket"]

    # 3. Verify Partial Position Close
    part_close_res = mt5.close_partial_position(ticket=ticket, lots_to_close=0.20, reason="TEST_PARTIAL_TP")
    assert part_close_res["status"] == "PARTIALLY_CLOSED"
    assert part_close_res["closed_lots"] == 0.20
    assert part_close_res["remaining_lots"] == 0.30

    pos = next(p for p in mt5.open_positions if p["ticket"] == ticket)
    assert pos["volume_lots"] == 0.30

    # 4. Verify MT5 Emergency Cancel-All Trigger
    emergency_report = mt5.emergency_cancel_all(flatten_positions=True)
    assert emergency_report["status"] == "EMERGENCY_CANCEL_ALL_COMPLETED"
    assert emergency_report["auto_trade_enabled"] is False
    assert len(mt5.open_positions) == 0, "Emergency cancel-all must flatten all open positions"

def test_backtest_and_monte_carlo():
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv("BTC/USDT", limit=100)
    engine = BacktestEngine(initial_capital=10000.0)
    res = engine.run(df, symbol="BTC/USDT")
    
    assert "total_net_profit" in res
    assert "win_rate_pct" in res
    assert "equity_curve" in res

    mc = MonteCarloSimulator.run_simulation([100, 200, -50, 150, -80], initial_capital=10000.0, num_simulations=100)
    assert "probability_of_profit_pct" in mc
    assert mc["probability_of_profit_pct"] >= 0.0

if __name__ == "__main__":
    print("Running OmniTrade AI Matrix Full Test Suite...")
    test_market_data_generation()
    print("Market Data test passed")
    test_technical_indicators()
    print("Technical Indicators test passed")
    test_smart_money_concepts()
    print("Smart Money Concepts test passed")
    test_ml_predictor()
    print("ML Predictor test passed")
    test_ai_consensus()
    print("AI Consensus Swarm test passed")
    test_risk_and_order_flow()
    print("Risk & Order Flow (Dynamic Slippage, Partial Fill, Emergency Cancel) passed")
    test_mt5_execution_bridges()
    print("MT5 Execution Bridges (Dynamic Slippage, Partial Lot Close, Emergency Kill Switch) passed")
    test_backtest_and_monte_carlo()
    print("Backtest & Monte Carlo test passed")
    print("\nALL 8 CORE AND EXECUTION TEST SUITES PASSED 100%!")
