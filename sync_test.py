import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.multi_exchange_sync import MultiExchangeSyncEngine

def run():
    engine = MultiExchangeSyncEngine()
    
    for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
        res = engine.fetch_multi_platform_ticker(sym)
        print(f"\n=======================================================")
        print(f"📊 REAL-TIME MULTI-EXCHANGE SYNC: {sym}")
        print(f"Global Composite VWAP: ${res['global_vwap']:,.2f}")
        print(f"Cross-Exchange Arbitrage Spread: ${res['cross_platform_arbitrage']['spread_usd']:,.2f} ({res['cross_platform_arbitrage']['spread_pct']}%)")
        print(f"Buy on: {res['cross_platform_arbitrage']['buy_on']} ➔ Sell on: {res['cross_platform_arbitrage']['sell_on']}")
        print(f"-------------------------------------------------------")
        for p in res["platforms"]:
            print(f"  {p['exchange']:12} | Price: ${p['price']:>10,.2f} | 24h Vol: {p['volume_24h']:>12,.1f} | 24h Chg: {p['change_24h']:>+6.2f}% | Latency: {p['latency_ms']}ms")

if __name__ == "__main__":
    run()
