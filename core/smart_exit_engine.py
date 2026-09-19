import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("OmniTrade.SmartExitEngine")

class SmartExitEngine:
    """
    Wall Street Institutional Stepped Trailing Stop-Loss,
    Dynamic Multi-Tier Partial Profit Taking, and Emergency Stop Engine.
    """

    @staticmethod
    def evaluate_position_exits(
        position: Dict[str, Any],
        current_price: float,
        atr: float
    ) -> Dict[str, Any]:
        """
        Evaluates a position for:
        1. Break-Even Stop Lock (Risk Elimination)
        2. Partial Take Profit 1 (TP1: +1.5R - Close 33% & lock +0.75R)
        3. Partial Take Profit 2 (TP2: +2.5R - Close 33% & lock +1.75R)
        4. Deep Trend Riding Trailing Stop (Final 34% runner)
        5. Hard Stop-Loss Hit
        """
        side = position.get("side", "BUY")
        entry_price = float(position.get("entry_price", 0.0))
        current_sl = float(position.get("sl", 0.0))
        amount = float(position.get("amount", position.get("units", 0.0)))
        tps = position.get("tp", [entry_price * 1.015, entry_price * 1.025, entry_price * 1.04])
        stage = position.get("exit_stage", 0) # 0: Initial, 1: Break-even, 2: TP1 Taken, 3: TP2 Taken

        atr_val = atr if atr > 0 else (entry_price * 0.012)
        r_dist = 1.5 * atr_val # 1R distance

        if side == "BUY":
            price_gain = current_price - entry_price
            r_multiple = price_gain / (r_dist + 1e-8)

            # Hard Stop-Loss Check
            if current_price <= current_sl and current_sl > 0:
                return {
                    "action": "FULL_CLOSE",
                    "reason": "HARD_STOP_LOSS_TRIGGERED",
                    "exit_price": current_price,
                    "close_pct": 1.0,
                    "new_sl": current_sl,
                    "stage": stage
                }

            # Stage 1: Break-Even Lock at +1.0R
            if r_multiple >= 1.0 and stage < 1:
                new_sl = round(entry_price + (atr_val * 0.1), 2) # Entry + minimal fee cushion
                return {
                    "action": "UPDATE_STOP_LOSS",
                    "reason": "BREAK_EVEN_RISK_ELIMINATION",
                    "new_sl": max(current_sl, new_sl),
                    "close_pct": 0.0,
                    "stage": 1,
                    "message": f"Locked Break-Even Stop at ${new_sl:,.2f} (Zero Risk Trade)"
                }

            # Stage 2: Partial TP1 (+1.5R) -> Close 33%, Lock SL to +0.75R
            if r_multiple >= 1.5 and stage < 2:
                new_sl = round(entry_price + (r_dist * 0.75), 2)
                return {
                    "action": "PARTIAL_CLOSE",
                    "reason": "TAKE_PROFIT_1_PARTIAL_CLOSE",
                    "close_pct": 0.33,
                    "exit_price": current_price,
                    "new_sl": max(current_sl, new_sl),
                    "stage": 2,
                    "message": f"Secured TP1: Closed 33% size @ ${current_price:,.2f}, SL raised to +0.75R (${new_sl:,.2f})"
                }

            # Stage 3: Partial TP2 (+2.5R) -> Close another 33%, Lock SL to +1.75R
            if r_multiple >= 2.5 and stage < 3:
                new_sl = round(entry_price + (r_dist * 1.75), 2)
                return {
                    "action": "PARTIAL_CLOSE",
                    "reason": "TAKE_PROFIT_2_PARTIAL_CLOSE",
                    "close_pct": 0.50, # 50% of remaining (effectively 33% of original)
                    "exit_price": current_price,
                    "new_sl": max(current_sl, new_sl),
                    "stage": 3,
                    "message": f"Secured TP2: Closed 33% size @ ${current_price:,.2f}, SL raised to +1.75R (${new_sl:,.2f})"
                }

            # Stage 4: Deep Trend Runner Trailing (Trailing by 1.2 * ATR below highest price)
            if stage >= 3:
                trail_sl = round(current_price - (atr_val * 1.2), 2)
                if trail_sl > current_sl:
                    return {
                        "action": "UPDATE_STOP_LOSS",
                        "reason": "DEEP_TREND_RUNNER_TRAIL",
                        "new_sl": trail_sl,
                        "close_pct": 0.0,
                        "stage": 4,
                        "message": f"Deep Runner Trailing Stop raised to ${trail_sl:,.2f}"
                    }

        elif side == "SELL":
            price_gain = entry_price - current_price
            r_multiple = price_gain / (r_dist + 1e-8)

            # Hard Stop-Loss Check
            if current_price >= current_sl and current_sl > 0:
                return {
                    "action": "FULL_CLOSE",
                    "reason": "HARD_STOP_LOSS_TRIGGERED",
                    "exit_price": current_price,
                    "close_pct": 1.0,
                    "new_sl": current_sl,
                    "stage": stage
                }

            # Stage 1: Break-Even Lock at +1.0R
            if r_multiple >= 1.0 and stage < 1:
                new_sl = round(entry_price - (atr_val * 0.1), 2)
                return {
                    "action": "UPDATE_STOP_LOSS",
                    "reason": "BREAK_EVEN_RISK_ELIMINATION",
                    "new_sl": min(current_sl, new_sl) if current_sl > 0 else new_sl,
                    "close_pct": 0.0,
                    "stage": 1,
                    "message": f"Locked Break-Even Short Stop at ${new_sl:,.2f}"
                }

            # Stage 2: Partial TP1 (+1.5R)
            if r_multiple >= 1.5 and stage < 2:
                new_sl = round(entry_price - (r_dist * 0.75), 2)
                return {
                    "action": "PARTIAL_CLOSE",
                    "reason": "TAKE_PROFIT_1_PARTIAL_CLOSE",
                    "close_pct": 0.33,
                    "exit_price": current_price,
                    "new_sl": new_sl,
                    "stage": 2,
                    "message": f"Secured Short TP1 @ ${current_price:,.2f}, SL lowered to ${new_sl:,.2f}"
                }

            # Stage 3: Partial TP2 (+2.5R)
            if r_multiple >= 2.5 and stage < 3:
                new_sl = round(entry_price - (r_dist * 1.75), 2)
                return {
                    "action": "PARTIAL_CLOSE",
                    "reason": "TAKE_PROFIT_2_PARTIAL_CLOSE",
                    "close_pct": 0.50,
                    "exit_price": current_price,
                    "new_sl": new_sl,
                    "stage": 3,
                    "message": f"Secured Short TP2 @ ${current_price:,.2f}, SL lowered to ${new_sl:,.2f}"
                }

            # Stage 4: Deep Trend Runner Trailing
            if stage >= 3:
                trail_sl = round(current_price + (atr_val * 1.2), 2)
                if trail_sl < current_sl:
                    return {
                        "action": "UPDATE_STOP_LOSS",
                        "reason": "DEEP_TREND_RUNNER_TRAIL",
                        "new_sl": trail_sl,
                        "close_pct": 0.0,
                        "stage": 4,
                        "message": f"Deep Runner Short Stop lowered to ${trail_sl:,.2f}"
                    }

        return {"action": "HOLD", "reason": "MAINTAINING_ACTIVE_PROFIT_RUN", "new_sl": current_sl, "stage": stage}
