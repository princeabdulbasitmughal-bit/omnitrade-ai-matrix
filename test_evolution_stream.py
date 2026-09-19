import asyncio
import websockets
import json
import sys

async def main():
    uri = "ws://localhost:8888/ws/stream"
    print(f"Connecting to {uri}...", flush=True)
    async with websockets.connect(uri) as ws:
        for i in range(2):
            raw = await ws.recv()
            msg = json.loads(raw)
            mtype = msg.get("type")
            print(f"\n--- [MESSAGE #{i+1}] Type: {mtype} ---", flush=True)
            data = msg.get("data", {})
            if mtype == "MARKET_TICK":
                evo = data.get("evolution", {})
                print(f"  * Evolution Step: #{evo.get('evolution_iteration')} | Epoch: {evo.get('active_epoch')}", flush=True)
                print(f"  * Loss: {evo.get('current_loss')} | Alpha Gain: +{evo.get('cumulative_alpha_gain_pct', 0):.2f}%", flush=True)
                ob = evo.get("orderbook_depth_imbalance", {})
                print(f"  * Order Flow Imbalance: {ob.get('imbalance_ratio')} ({ob.get('order_flow_bias')})", flush=True)
                port = data.get("portfolio", {})
                print(f"  * Live Portfolio Equity: ${port.get('equity')} | Unrealized PnL: ${port.get('total_unrealized_pnl')}", flush=True)
                mt5 = data.get("mt5", {})
                print(f"  * MT5 Live Equity: ${mt5.get('equity')} | XAUUSD: ${mt5.get('xauusd_live_price')}", flush=True)
            elif mtype == "INIT_STATE":
                port = data.get("portfolio", {})
                print(f"  * Init Portfolio Equity: ${port.get('equity')}", flush=True)
                evo = data.get("evolution", {})
                print(f"  * Init Evolution: Adapter {evo.get('active_adapter')} | Loss: {evo.get('current_loss')}", flush=True)

asyncio.run(main())
