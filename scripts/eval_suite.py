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
print('Signal:', res.get('signal'))
print('Confidence:', f"{res.get('confidence', 0)*100:.1f}%")
print('Weighted Score:', res.get('weighted_score'))
for model, vote in res.get('model_votes', {}).items():
    print(f"  {model}: {vote}")

print('\n=== SCALPER STATUS ===')
with open(r'E:\scalping-robot-v5\live_status.json', encoding='utf-8') as f:
    s = json.load(f)
print('Status:', s.get('status'))
print('Equity:', s.get('equity'), '| Balance:', s.get('balance'))
print('Latency Metrics:', s.get('latency_metrics'))
print('Daily PnL:', s.get('daily_pnl'))
print('Spread Pips:', s.get('spread_pips'))
