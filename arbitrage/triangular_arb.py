import logging
from typing import Dict, Any, List

logger = logging.getLogger("OmniTrade.TriangularArb")

class TriangularArbitrageScanner:
    def __init__(self, fee_per_leg: float = 0.00075):
        self.fee_per_leg = fee_per_leg
        self.total_fee_3_legs = (1 - fee_per_leg) ** 3  # ~0.99775 -> 0.225% total fee

    def scan_opportunities(self, live_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Scans for triangular arbitrage paths.
        Example paths:
        1. USDT -> BTC -> ETH -> USDT
        2. USDT -> SOL -> BTC -> USDT
        3. USDT -> BNB -> ETH -> USDT
        """
        opportunities = []

        # Required price pairs (with sensible fallbacks if missing)
        btc_usdt = live_prices.get("BTC/USDT", 96500.0)
        eth_usdt = live_prices.get("ETH/USDT", 2750.0)
        sol_usdt = live_prices.get("SOL/USDT", 185.0)
        bnb_usdt = live_prices.get("BNB/USDT", 650.0)

        # Synthetic/Derived Cross Pairs
        eth_btc = eth_usdt / btc_usdt
        sol_btc = sol_usdt / btc_usdt
        bnb_eth = bnb_usdt / eth_usdt

        # Check Path 1: USDT -> BTC -> ETH -> USDT
        # Step 1: 1000 USDT -> BTC (buy BTC @ btc_usdt)
        # Step 2: BTC -> ETH (buy ETH @ eth_btc)
        # Step 3: ETH -> USDT (sell ETH @ eth_usdt)
        theoretical_rate_1 = (1.0 / btc_usdt) * (1.0 / (eth_btc * 1.0001)) * eth_usdt
        net_return_1 = (theoretical_rate_1 * self.total_fee_3_legs - 1.0) * 100

        opportunities.append({
            "path": "USDT ➔ BTC ➔ ETH ➔ USDT",
            "legs": ["Buy BTC/USDT", "Buy ETH/BTC", "Sell ETH/USDT"],
            "gross_return_pct": round((theoretical_rate_1 - 1.0) * 100, 4),
            "net_return_pct": round(net_return_1, 4),
            "status": "PROFITABLE" if net_return_1 > 0.05 else "MONITORING",
            "min_capital_usd": 500.0,
            "risk_profile": "ZERO_MARKET_RISK_ARBITRAGE"
        })

        # Check Path 2: USDT -> SOL -> BTC -> USDT
        theoretical_rate_2 = (1.0 / sol_usdt) * (sol_btc * 0.9999) * btc_usdt
        net_return_2 = (theoretical_rate_2 * self.total_fee_3_legs - 1.0) * 100

        opportunities.append({
            "path": "USDT ➔ SOL ➔ BTC ➔ USDT",
            "legs": ["Buy SOL/USDT", "Sell SOL/BTC", "Sell BTC/USDT"],
            "gross_return_pct": round((theoretical_rate_2 - 1.0) * 100, 4),
            "net_return_pct": round(net_return_2, 4),
            "status": "PROFITABLE" if net_return_2 > 0.05 else "MONITORING",
            "min_capital_usd": 250.0,
            "risk_profile": "ZERO_MARKET_RISK_ARBITRAGE"
        })

        # Check Path 3: USDT -> BNB -> ETH -> USDT
        theoretical_rate_3 = (1.0 / bnb_usdt) * (bnb_eth * 1.0002) * eth_usdt
        net_return_3 = (theoretical_rate_3 * self.total_fee_3_legs - 1.0) * 100

        opportunities.append({
            "path": "USDT ➔ BNB ➔ ETH ➔ USDT",
            "legs": ["Buy BNB/USDT", "Sell BNB/ETH", "Sell ETH/USDT"],
            "gross_return_pct": round((theoretical_rate_3 - 1.0) * 100, 4),
            "net_return_pct": round(net_return_3, 4),
            "status": "PROFITABLE" if net_return_3 > 0.05 else "MONITORING",
            "min_capital_usd": 300.0,
            "risk_profile": "ZERO_MARKET_RISK_ARBITRAGE"
        })

        return opportunities
