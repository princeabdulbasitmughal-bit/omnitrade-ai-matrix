import logging
from typing import Dict, Any, Tuple, Optional
from config.settings import Config
from core.portfolio import Portfolio

logger = logging.getLogger("OmniTrade.RiskEngine")

class RiskEngine:
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.max_risk_pct = Config.MAX_RISK_PER_TRADE_PCT
        self.max_daily_dd = Config.MAX_DAILY_DRAWDOWN_PCT
        self.is_circuit_broken = False

    def check_circuit_breaker(self) -> Tuple[bool, str]:
        """Checks if daily drawdown limit is breached. Auto-locks new trades if breached."""
        summary = self.portfolio.get_summary()
        daily_dd = summary["daily_drawdown_pct"]
        if daily_dd >= self.max_daily_dd:
            self.is_circuit_broken = True
            msg = f"CIRCUIT BREAKER TRIGGERED: Daily drawdown is {daily_dd:.2f}% (Limit: {self.max_daily_dd}%). Trading paused for capital protection."
            logger.warning(msg)
            return True, msg
        self.is_circuit_broken = False
        return False, "Normal Risk Operations"

    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss_price: float, atr: float = 0.0) -> float:
        """
        Calculates optimal position size using Fixed Fractional Risk & ATR Volatility adjustment.
        Never risks more than Config.MAX_RISK_PER_TRADE_PCT of total account equity.
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        equity = self.portfolio.equity
        risk_capital = equity * (self.max_risk_pct / 100.0)

        # Risk per unit
        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit <= 0:
            # Default to 1.5% price difference if SL is degenerate
            risk_per_unit = entry_price * 0.015

        units = risk_capital / risk_per_unit

        # Capital ceiling: Do not allocate more than 25% of total cash to a single asset
        max_cost = self.portfolio.cash * 0.25
        max_units = max_cost / entry_price if entry_price > 0 else 0
        units = min(units, max_units)

        # Formatting based on asset price magnitude
        if entry_price > 1000:
            return round(units, 4)
        elif entry_price > 10:
            return round(units, 2)
        else:
            return round(units, 1)

    def calculate_sl_tp(self, side: str, entry_price: float, atr: float) -> Tuple[float, list]:
        """
        Calculates dynamic Stop-Loss and Multi-tier Take-Profit targets.
        - Stop Loss = Entry - 1.5 * ATR (for BUY)
        - TP1 (1:1.5 RR)
        - TP2 (1:2.5 RR)
        - TP3 (1:4.0 RR)
        """
        if atr <= 0 or atr is None:
            atr = entry_price * 0.012  # Fallback: 1.2% volatility

        sl_distance = 1.5 * atr

        if side == "BUY":
            sl = round(entry_price - sl_distance, 4 if entry_price > 10 else 6)
            tp1 = round(entry_price + (sl_distance * 1.5), 4 if entry_price > 10 else 6)
            tp2 = round(entry_price + (sl_distance * 2.5), 4 if entry_price > 10 else 6)
            tp3 = round(entry_price + (sl_distance * 4.0), 4 if entry_price > 10 else 6)
        else: # SELL / SHORT
            sl = round(entry_price + sl_distance, 4 if entry_price > 10 else 6)
            tp1 = round(entry_price - (sl_distance * 1.5), 4 if entry_price > 10 else 6)
            tp2 = round(entry_price - (sl_distance * 2.5), 4 if entry_price > 10 else 6)
            tp3 = round(entry_price - (sl_distance * 4.0), 4 if entry_price > 10 else 6)

        return sl, [tp1, tp2, tp3]

    def evaluate_active_positions(self, current_prices: Dict[str, float], atrs: Dict[str, float] = None) -> list:
        """
        Monitors active positions against Stop Loss, Take Profit targets, and updates Trailing Stop.
        Returns list of closed position records.
        """
        closed_trades = []
        atrs = atrs or {}

        for symbol, pos in list(self.portfolio.positions.items()):
            price = current_prices.get(symbol)
            if price is None:
                continue

            side = pos["side"]
            sl = pos["sl"]
            tps = pos["tp"]
            entry_price = pos["entry_price"]
            atr = atrs.get(symbol, entry_price * 0.01)

            # Update high/low tracking for trailing stop
            if side == "BUY":
                if price > pos.get("highest_price", entry_price):
                    pos["highest_price"] = price
                    # Trailing Stop: If in profit by >= 1.5x ATR, trail SL behind highest price
                    if price >= entry_price + (1.5 * atr):
                        new_sl = round(price - (1.5 * atr), 4 if price > 10 else 6)
                        if new_sl > sl:
                            pos["sl"] = new_sl
                            logger.info(f"Trailing SL adjusted UP for {symbol}: ${new_sl:.2f}")

                # Check Stop-Loss hit
                if price <= pos["sl"]:
                    record = self.portfolio.close_position(symbol, price, exit_reason="STOP_LOSS")
                    if record:
                        closed_trades.append(record)
                    continue

                # Check TP3 (Final target)
                if len(tps) >= 3 and price >= tps[2]:
                    record = self.portfolio.close_position(symbol, price, exit_reason="TAKE_PROFIT_3 (Final)")
                    if record:
                        closed_trades.append(record)
                    continue

            elif side == "SELL":
                if price < pos.get("lowest_price", entry_price):
                    pos["lowest_price"] = price
                    if price <= entry_price - (1.5 * atr):
                        new_sl = round(price + (1.5 * atr), 4 if price > 10 else 6)
                        if new_sl < sl:
                            pos["sl"] = new_sl
                            logger.info(f"Trailing SL adjusted DOWN for {symbol}: ${new_sl:.2f}")

                # Check Stop-Loss hit
                if price >= pos["sl"]:
                    record = self.portfolio.close_position(symbol, price, exit_reason="STOP_LOSS")
                    if record:
                        closed_trades.append(record)
                    continue

                # Check TP3 hit
                if len(tps) >= 3 and price <= tps[2]:
                    record = self.portfolio.close_position(symbol, price, exit_reason="TAKE_PROFIT_3 (Final)")
                    if record:
                        closed_trades.append(record)
                    continue

        return closed_trades
