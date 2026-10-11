import sys, json, os

sys.path.insert(0, r'E:\omnitrade-ai-matrix')
from ai_swarm.consensus_matrix import AIConsensusMatrix

cm = AIConsensusMatrix()
res = cm.evaluate_market_consensus(
    'BTC/USDT',
    {'trend': 'bullish', 'ema_cross': True, 'rsi': 58.2},
    {'liquidity_sweep': True, 'ob_zone': '64200-64500', 'structure': 'bullish'},
    {'lstm_prob': 0.68, 'rf_pred': 'BUY'},
    {'change_24h': 2.4, 'volume_spike': True}
)

print('=== BASIT2 CONSENSUS ===')
print('Final Signal:', res.get('final_signal'))
print('Aggregate Confidence:', f"{res.get('aggregate_confidence', 0)*100:.1f}%")
print('Consensus Score:', res.get('consensus_score'))
print('Threshold Met:', res.get('threshold_met'))
print('Adaptive Weights:', res.get('adaptive_weights_applied'))
for agent in res.get('swarm_deliberation', []):
    name = agent.get('agent') or agent.get('agent_name', 'Agent')
    print(f"  {name}: {agent.get('signal')} ({agent.get('confidence', 0)*100:.1f}%)")

print('\n=== SCALPER STATUS ===')
with open(r'E:\scalping-robot-v5\live_status.json', encoding='utf-8') as f:
    s = json.load(f)
print('Status:', s.get('status'))
print('Equity:', s.get('equity'), '| Balance:', s.get('balance'))
print('Latency Metrics:', s.get('latency_metrics'))
print('Daily PnL:', s.get('daily_pnl'))
print('Spread Pips:', s.get('spread_pips'))
