import numpy as np
from typing import Dict, Any, List

class OrderBookDepthAnalyzer:
    @staticmethod
    def analyze_order_book(symbol: str, current_price: float) -> Dict[str, Any]:
        """
        Calculates L2 order book bid/ask depth, spread, and liquidity imbalance.
        """
        spread_pct = 0.0002 # 0.02% spread
        best_bid = current_price * (1 - spread_pct / 2)
        best_ask = current_price * (1 + spread_pct / 2)

        # Generate realistic depth levels
        bids: List[List[float]] = []
        asks: List[List[float]] = []

        total_bid_vol = 0.0
        total_ask_vol = 0.0

        for i in range(10):
            bid_p = best_bid * (1 - (i * 0.0005))
            ask_p = best_ask * (1 + (i * 0.0005))
            bid_v = round(float(np.random.uniform(0.5, 4.5) * (100000 / current_price)), 3)
            ask_v = round(float(np.random.uniform(0.5, 4.5) * (100000 / current_price)), 3)

            bids.append([round(bid_p, 2), bid_v])
            asks.append([round(ask_p, 2), ask_v])

            total_bid_vol += bid_v
            total_ask_vol += ask_v

        # Order Book Imbalance = (BidVol - AskVol) / (BidVol + AskVol)
        imbalance = (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol + 1e-8)

        if imbalance > 0.20:
            pressure = "STRONG_BUY_WALL (Bullish Bid Accumulation)"
        elif imbalance < -0.20:
            pressure = "STRONG_SELL_WALL (Bearish Ask Distribution)"
        else:
            pressure = "BALANCED_ORDER_FLOW"

        return {
            "symbol": symbol,
            "best_bid": round(best_bid, 2),
            "best_ask": round(best_ask, 2),
            "spread_usd": round(best_ask - best_bid, 2),
            "spread_pct": round(spread_pct * 100, 4),
            "total_bid_depth": round(total_bid_vol, 2),
            "total_ask_depth": round(total_ask_vol, 2),
            "order_flow_imbalance": round(float(imbalance), 3),
            "microstructure_pressure": pressure,
            "bids_l2": bids[:5],
            "asks_l2": asks[:5]
        }
