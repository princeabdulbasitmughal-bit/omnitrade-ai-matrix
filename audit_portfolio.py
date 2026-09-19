import requests
import json

def audit():
    try:
        res = requests.get('http://localhost:8888/api/portfolio')
        if res.status_code == 200:
            p = res.json()
            print("==================================================")
            print("🚀 OMNITRADE PRO 1-MINUTE LIVE AUDIT REPORT")
            print(f"Equity: ${p.get('equity', 0):,.2f}")
            print(f"Cash: ${p.get('cash', 0):,.2f}")
            print(f"Net PnL: +${p.get('total_pnl', 0):,.2f} (+{p.get('total_pnl_pct', 0):.2f}%)")
            print(f"Win Rate: {p.get('win_rate', 0):.1f}% ({p.get('wins', 0)}W / {p.get('losses', 0)}L)")
            print(f"Open Positions Count: {p.get('open_positions_count', 0)}")
            print("--------------------------------------------------")
            for pos in p.get('open_positions', []):
                print(f"  • {pos['symbol']} [{pos['side']}] | Units: {pos['amount']} | Entry: ${pos.get('entry_price', 0):,.2f} | Current: ${pos.get('current_price', pos.get('entry_price', 0)):,.2f} | PnL: ${pos.get('unrealized_pnl', 0):+,.2f} ({pos.get('unrealized_pnl_pct', 0):+.2f}%) | SL: ${pos.get('sl', 0):,.2f}")
            print("==================================================")
    except Exception as e:
        print("Audit error:", e)

if __name__ == "__main__":
    audit()
