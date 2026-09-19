import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger("OmniTrade.ProfitShare")

class ProfitShareEngine:
    """
    Institutional 20% High-Water Mark (HWM) Performance Fee Deductor.
    Allows you to monetize copy-traders, prop firm allocations, and external investors.
    """
    PERFORMANCE_FEE_PCT = 0.20 # 20% Performance Carry Fee

    @staticmethod
    def calculate_performance_fee(
        client_id: str,
        starting_equity: float,
        current_equity: float,
        previous_high_water_mark: float
    ) -> Dict[str, Any]:
        """
        Calculates 20% performance fee based on net new profits above High-Water Mark.
        """
        net_profit = current_equity - starting_equity
        new_high = max(current_equity, previous_high_water_mark)
        excess_profit_above_hwm = max(0.0, current_equity - previous_high_water_mark)

        fee_amount = round(excess_profit_above_hwm * ProfitShareEngine.PERFORMANCE_FEE_PCT, 2)
        net_client_profit = round(net_profit - fee_amount, 2)

        return {
            "client_id": client_id,
            "starting_equity": round(starting_equity, 2),
            "current_equity": round(current_equity, 2),
            "total_gross_profit": round(net_profit, 2),
            "previous_hwm": round(previous_high_water_mark, 2),
            "new_hwm": round(new_high, 2),
            "performance_fee_earned_usd": fee_amount,
            "performance_fee_rate": "20.0%",
            "net_client_profit_usd": net_client_profit,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "FEE_COLLECTIBLE" if fee_amount > 0 else "NO_FEE_BELOW_HWM"
        }
