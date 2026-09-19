import sys
import os
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.market_data import MarketDataProvider
from rl_engine.env import TradingEnvironment
from rl_engine.ppo_agent import PPOTradingAgent
from rl_engine.dqn_agent import DQNAgent
from arbitrage.triangular_arb import TriangularArbitrageScanner
from arbitrage.orderbook_depth import OrderBookDepthAnalyzer
from voice_engine.voice_broadcaster import VoiceAudioBroadcaster
from marketplace.strategy_catalog import StrategyMarketplace
from saas.billing_tiers import BillingTiersManager
from saas.webhooks import WebhookManager
from saas.auth import MultiTenantAuth

def test_rl_environment_and_agents():
    provider = MarketDataProvider()
    df = provider.fetch_ohlcv("BTC/USDT", limit=50)
    
    env = TradingEnvironment(df, initial_balance=10000.0)
    state = env.reset()
    assert len(state) == 12
    assert not np.isnan(state).any()

    # Test PPO Agent
    ppo = PPOTradingAgent(state_dim=12, action_dim=3)
    action, log_prob, val = ppo.select_action(state)
    assert action in [0, 1, 2]
    
    ppo_sig = ppo.get_signal_and_confidence(state)
    assert ppo_sig["signal"] in ["HOLD", "BUY", "SELL"]
    assert 0.0 <= ppo_sig["confidence"] <= 1.0

    # Test DQN Agent
    dqn = DQNAgent(state_dim=12, action_dim=3)
    dqn_eval = dqn.evaluate(state)
    assert dqn_eval["signal"] in ["HOLD", "BUY", "SELL"]

    # Step in environment
    next_s, reward, done, info = env.step(action)
    assert len(next_s) == 12
    assert "equity" in info

def test_arbitrage_and_microstructure():
    scanner = TriangularArbitrageScanner()
    prices = {"BTC/USDT": 96500.0, "ETH/USDT": 2750.0, "SOL/USDT": 185.0, "BNB/USDT": 650.0}
    opps = scanner.scan_opportunities(prices)
    assert len(opps) == 3
    assert all("gross_return_pct" in o for o in opps)

    depth = OrderBookDepthAnalyzer.analyze_order_book("BTC/USDT", 96500.0)
    assert "best_bid" in depth
    assert "order_flow_imbalance" in depth
    assert depth["best_ask"] > depth["best_bid"]

def test_voice_and_marketplace():
    voice = VoiceAudioBroadcaster()
    script = voice.generate_trade_speech_script("TRADE_OPEN", {"symbol": "BTC/USDT", "side": "BUY", "entry_price": 96500.0, "sl": 95000.0})
    assert "OmniTrade" in script
    assert "96,500.00" in script

    mkt = StrategyMarketplace()
    strats = mkt.list_strategies()
    assert len(strats) == 5
    
    copy_res = mkt.copy_strategy("strat_smc_fvg")
    assert copy_res["status"] == "ACTIVATED"

def test_saas_and_webhooks():
    plans = BillingTiersManager.get_plans()
    assert len(plans) == 3

    auth = MultiTenantAuth()
    key = auth.generate_api_key("usr_test_vip", "VIP Hedge Fund Key")
    assert auth.validate_api_key(key)

    # TradingView webhook test
    tv_res = WebhookManager.process_tradingview_alert({
        "ticker": "BTCUSDT",
        "action": "BUY",
        "price": 96500.0,
        "strategy": "SuperTrend_PPO"
    })
    assert tv_res["symbol"] == "BTC/USDT"
    assert tv_res["action"] == "BUY"

    # MT5 bridge test
    mt5_res = WebhookManager.process_mt5_bridge_event({
        "symbol": "XAU/USD",
        "cmd": "BUY",
        "price": 2920.0,
        "volume": 1.0
    })
    assert mt5_res["symbol"] == "XAU/USD"

if __name__ == "__main__":
    print("Testing Commercial SaaS & RL Suite...")
    test_rl_environment_and_agents()
    print("✓ RL Environment, PPO & DQN agents verified")
    test_arbitrage_and_microstructure()
    print("✓ Triangular Arbitrage & Order Book Microstructure verified")
    test_voice_and_marketplace()
    print("✓ Voice Audio commentary & Strategy Marketplace verified")
    test_saas_and_webhooks()
    print("✓ SaaS Billing, Auth & Webhooks (TradingView/MT5) verified")
    print("\nALL COMMERCIAL EXTENSIONS PASSED 100%!")
