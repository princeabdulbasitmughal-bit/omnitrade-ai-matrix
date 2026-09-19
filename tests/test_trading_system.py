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
    assert pred["prediction"] in ["BULLISH", "BEARISH", "NEUTRAL"]
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
    print("✓ Market Data test passed")
    test_technical_indicators()
    print("✓ Technical Indicators test passed")
    test_smart_money_concepts()
    print("✓ Smart Money Concepts test passed")
    test_ml_predictor()
    print("✓ ML Predictor test passed")
    test_ai_consensus()
    print("✓ AI Consensus Swarm test passed")
    test_risk_and_order_flow()
    print("✓ Risk & Order Flow test passed")
    test_backtest_and_monte_carlo()
    print("✓ Backtest & Monte Carlo test passed")
    print("\nALL 7 CORE TEST SUITES PASSED 100%!")
