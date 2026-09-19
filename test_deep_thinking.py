import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_swarm.deep_thinking_vision_engine import DeepThinkingVisionEngine
from core.smart_exit_engine import SmartExitEngine
from core.market_data import MarketDataProvider
from strategies.indicators import TechnicalIndicators
from strategies.smart_money_concepts import SmartMoneyConcepts
from core.order_flow_heatmap import OrderFlowAnalytics

def run_test():
    md = MarketDataProvider()
    df = md.fetch_ohlcv('BTC/USDT', limit=60)
    price = md.get_current_ticker('BTC/USDT').get('last', 72000.0)

    tech = TechnicalIndicators.get_latest_summary(df)
    smc = SmartMoneyConcepts.get_smc_summary(df)
    cvd = OrderFlowAnalytics.calculate_cumulative_volume_delta(df)
    vision = DeepThinkingVisionEngine.analyze_chart_geometry_vision(df)
    cot = DeepThinkingVisionEngine.generate_chain_of_thought_deep_thinking('BTC/USDT', price, tech, smc, vision, cvd)

    print("==================================================")
    print("🧠 MULTI-MODAL VISION & DEEP THINKING ALPHA REPORT")
    print(f"Asset: BTC/USDT @ ${price:,.2f}")
    print(f"Geometric Chart Pattern: {vision['primary_pattern']} ({vision['confidence']*100:.0f}% Match)")
    print(f"Pattern Analysis: {vision['description']}")
    print("--------------------------------------------------")
    print(f"⚡ 5-Step Deep Thinking Alpha Verdict: {cot['verdict']} ({cot['deep_thinking_confidence']*100:.1f}%)")
    for step in cot['chain_of_thought_steps']:
        print(f"\n  [Step {step['step']}]")
        print(f"   {step['reasoning']}")
    print("==================================================")

    # Test Smart Stepped Exit Engine
    test_pos = {"side": "BUY", "entry_price": 70000.0, "sl": 69000.0, "amount": 0.05, "exit_stage": 0}
    exit_eval = SmartExitEngine.evaluate_position_exits(test_pos, 72000.0, 800.0)
    print(f"\nSmart Exit Evaluation @ $72,000 (+2.5R): Action={exit_eval['action']}, Reason={exit_eval['reason']}, New SL=${exit_eval.get('new_sl', 0):,.2f}")

if __name__ == "__main__":
    run_test()
