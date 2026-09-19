import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Config
from core.market_data import MarketDataProvider
from strategies.strategy_orchestrator import StrategyOrchestrator
from core.portfolio import Portfolio
from core.risk_engine import RiskEngine
from core.order_manager import OrderManager
from ai_swarm.consensus_matrix import AIConsensusMatrix
from rl_engine.ppo_agent import PPOTradingAgent

def generate_live_signals():
    market_data = MarketDataProvider()
    portfolio = Portfolio()
    risk_engine = RiskEngine(portfolio)
    order_manager = OrderManager(portfolio, risk_engine)
    consensus_matrix = AIConsensusMatrix()
    orchestrator = StrategyOrchestrator(market_data, portfolio, risk_engine, order_manager, consensus_matrix)
    ppo = PPOTradingAgent()

    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XAU/USD", "EUR/USD", "NVDA"]
    signals_output = []

    for sym in symbols:
        try:
            res = orchestrator.analyze_symbol(sym)
            ticker = res["ticker"]
            tech = res["technical_indicators"]
            smc = res["smart_money_concepts"]
            ml = res["ml_prediction"]
            ai = res["ai_consensus"]
            price = ticker.get("last", 0.0)
            atr = tech.get("atr", price * 0.012)
            
            sig = ai.get("final_signal", "HOLD")
            action_dir = "SELL" if "SELL" in sig else "BUY"
            sl, tps = risk_engine.calculate_sl_tp(action_dir, price, atr)

            signals_output.append({
                "symbol": sym,
                "price": price,
                "change_24h": ticker.get("change_24h", 0.0),
                "signal": sig,
                "confidence": round(ai.get("aggregate_confidence", 0.5) * 100, 1),
                "ml_prediction": ml.get("prediction", "NEUTRAL"),
                "supertrend": "BULL 🟢" if tech.get("supertrend_is_bull") else "BEAR 🔴",
                "rsi": tech.get("rsi", 50.0),
                "smc_structure": smc.get("market_structure", "RANGING"),
                "fvg_bullish": smc.get("bullish_fvg_present", False),
                "entry_price": price,
                "stop_loss": sl,
                "take_profit_1": tps[0],
                "take_profit_2": tps[1],
                "take_profit_3": tps[2],
                "risk_reward_ratio": "1:2.5",
                "ai_rationale": ai.get("summary_thesis", "")
            })
        except Exception as e:
            print(f"Error analyzing {sym}: {e}")

    print(json.dumps(signals_output, indent=2))

if __name__ == "__main__":
    generate_live_signals()
