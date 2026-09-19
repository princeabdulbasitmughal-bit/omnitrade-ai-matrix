from core.autonomous_evolution_engine import evolution_engine
from core.live_reality_engine import live_reality

res = evolution_engine.execute_loop_evolution_step(
    live_market_data=live_reality.get_real_data_summary(),
    portfolio_data=live_reality.get_portfolio(),
    mt5_data=live_reality.get_mt5_account()
)

print("=== EVOLUTION STEP TEST ===")
print(f"Iteration: #{res.get('evolution_iteration')}")
print(f"Active Adapter: {res.get('active_adapter')} | Epoch: {res.get('active_epoch')}")
print(f"Loss: {res.get('current_loss')} | Cumulative Alpha: +{res.get('cumulative_alpha_gain_pct')}%")
ob = res.get('orderbook_depth_imbalance', {})
print(f"Order Flow Bias: {ob.get('order_flow_bias')} (Ratio: {ob.get('imbalance_ratio')})")
print(f"Stepped Smart Exits Active: {len(res.get('stepped_smart_exits', []))}")
for s in res.get('stepped_smart_exits', []):
    print(f"  {s.get('symbol')} Entry: ${s.get('entry_price')} -> StopLoss: ${s.get('dynamic_stop_loss')} ({s.get('active_tier')})")
