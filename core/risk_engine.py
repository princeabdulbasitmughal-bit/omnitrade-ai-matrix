import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
import numpy as np

from config.settings import Config
from core.portfolio import Portfolio

logger = logging.getLogger("OmniTrade.RiskEngine")

class RiskEngine:
    """
    Wall Street Institutional-Grade Risk Engine for OmniTrade AI Matrix.
    
    Validates and enforces:
    1. Drawdown Limits: Dual Daily Drawdown (3.0%) and Peak-to-Trough Portfolio Drawdown (6.0%).
    2. Multi-Tier Circuit Breakers: Hard halt on breach, consecutive loss lock, and soft de-rating.
    3. Position Sizing: Fixed-Fractional Risk, Fractional Kelly Criterion, Volatility ATR adjustments, 
       and 25% single-asset cash capital ceiling.
    4. Monte Carlo Profit Probability Simulations: Bootstrap resampling, path-dependent ruin tracking,
       confidence intervals, and Value-at-Risk (VaR / CVaR).
    """

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.max_risk_pct = getattr(Config, "MAX_RISK_PER_TRADE_PCT", 1.5)
        self.max_daily_dd = getattr(Config, "MAX_DAILY_DRAWDOWN_PCT", 3.0)
        self.max_total_dd = getattr(Config, "MAX_TOTAL_DRAWDOWN_PCT", 6.0)
        self.max_consecutive_losses = getattr(Config, "MAX_CONSECUTIVE_LOSSES", 4)
        
        # State tracking
        self.is_circuit_broken = False
        self.circuit_breaker_reason = ""
        self.circuit_breaker_timestamp = None
        self.soft_circuit_active = False

    def check_circuit_breaker(self) -> Tuple[bool, str]:
        """
        Evaluates real-time drawdown and portfolio health across multiple circuit breaker tiers:
        - Daily Drawdown Threshold (Hard Halt)
        - Max Peak-to-Trough Drawdown Threshold (Emergency Halt)
        - Consecutive Losses Threshold (Cooldown Lock)
        - Soft Warning Threshold (Precautionary Risk De-Rating)
        """
        summary = self.portfolio.get_summary()
        daily_dd = summary.get("daily_drawdown_pct", 0.0)
        max_dd = summary.get("max_drawdown_pct", 0.0)
        consecutive_losses = summary.get("consecutive_losses", 0)

        # 1. Emergency Peak-to-Trough Drawdown Circuit Breaker
        if max_dd >= self.max_total_dd:
            self.is_circuit_broken = True
            self.circuit_breaker_reason = f"MAX TOTAL DRAWDOWN BREACH: Current drawdown from peak is {max_dd:.2f}% (Limit: {self.max_total_dd}%)."
            self.circuit_breaker_timestamp = datetime.utcnow().isoformat()
            logger.critical(f"EMERGENCY CIRCUIT BREAKER ACTIVATED: {self.circuit_breaker_reason}")
            return True, self.circuit_breaker_reason

        # 2. Daily Drawdown Circuit Breaker
        if daily_dd >= self.max_daily_dd:
            self.is_circuit_broken = True
            self.circuit_breaker_reason = f"DAILY DRAWDOWN BREACH: Daily drawdown is {daily_dd:.2f}% (Limit: {self.max_daily_dd}%)."
            self.circuit_breaker_timestamp = datetime.utcnow().isoformat()
            logger.warning(f"CIRCUIT BREAKER TRIGGERED: {self.circuit_breaker_reason}")
            return True, self.circuit_breaker_reason

        # 3. Consecutive Losses Circuit Breaker
        if consecutive_losses >= self.max_consecutive_losses:
            self.is_circuit_broken = True
            self.circuit_breaker_reason = f"CONSECUTIVE LOSSES BREACH: {consecutive_losses} consecutive loss trades recorded (Limit: {self.max_consecutive_losses}). Cooldown enforced."
            self.circuit_breaker_timestamp = datetime.utcnow().isoformat()
            logger.warning(f"CIRCUIT BREAKER TRIGGERED: {self.circuit_breaker_reason}")
            return True, self.circuit_breaker_reason

        # 4. Soft Circuit Precautionary Risk De-Rating (Daily DD >= 70% of limit)
        if daily_dd >= (self.max_daily_dd * 0.70):
            self.soft_circuit_active = True
            logger.info(f"Soft risk de-rating activated: Daily drawdown {daily_dd:.2f}% reached warning zone.")
        else:
            self.soft_circuit_active = False

        self.is_circuit_broken = False
        self.circuit_breaker_reason = ""
        return False, "Normal Risk Operations: All limits healthy"

    def reset_circuit_breaker(self, admin_override: bool = False) -> Tuple[bool, str]:
        """
        Resets circuit breaker status if risk metrics have returned to safe boundaries
        or if admin override is explicitly supplied.
        """
        summary = self.portfolio.get_summary()
        daily_dd = summary.get("daily_drawdown_pct", 0.0)
        max_dd = summary.get("max_drawdown_pct", 0.0)

        if not admin_override:
            if daily_dd >= self.max_daily_dd or max_dd >= self.max_total_dd:
                msg = f"Cannot reset circuit breaker: Daily DD ({daily_dd:.2f}%) or Total DD ({max_dd:.2f}%) still breaches limits."
                logger.warning(msg)
                return False, msg

        self.is_circuit_broken = False
        self.circuit_breaker_reason = ""
        self.circuit_breaker_timestamp = None
        self.soft_circuit_active = False
        msg = "Circuit breaker successfully reset to normal status."
        logger.info(msg)
        return True, msg

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic status of all circuit breaker thresholds."""
        summary = self.portfolio.get_summary()
        return {
            "is_circuit_broken": self.is_circuit_broken,
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "circuit_breaker_timestamp": self.circuit_breaker_timestamp,
            "soft_circuit_active": self.soft_circuit_active,
            "metrics": {
                "daily_drawdown_pct": summary.get("daily_drawdown_pct", 0.0),
                "max_drawdown_pct": summary.get("max_drawdown_pct", 0.0),
                "consecutive_losses": summary.get("consecutive_losses", 0),
                "equity": summary.get("equity", 0.0),
                "cash": summary.get("cash", 0.0)
            },
            "thresholds": {
                "max_daily_dd_pct": self.max_daily_dd,
                "max_total_dd_pct": self.max_total_dd,
                "max_consecutive_losses": self.max_consecutive_losses,
                "max_risk_per_trade_pct": self.max_risk_pct
            }
        }

    def calculate_position_size(
        self, 
        symbol: str, 
        entry_price: float, 
        stop_loss_price: float, 
        atr: float = 0.0,
        apply_kelly: bool = True
    ) -> float:
        """
        Calculates optimal position size using Fixed Fractional Risk, Volatility (ATR) adjustment,
        Fractional Kelly scaling, and a 25% single-asset cash capital ceiling.
        
        Mathematical Formulation:
            Risk Capital = Equity * (Max Risk % / 100) * [Soft Circuit Factor] * [Kelly Multiplier]
            Risk Per Unit = max(|Entry - Stop Loss|, 0.5 * ATR)
            Raw Units = Risk Capital / Risk Per Unit
            Units = min(Raw Units, (0.25 * Free Cash) / Entry)
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        equity = self.portfolio.equity
        if equity <= 0:
            return 0.0

        # Base Fixed-Fractional Risk
        risk_pct = self.max_risk_pct
        if self.soft_circuit_active:
            # Precautionary 50% risk de-rating during elevated daily drawdown
            risk_pct = risk_pct * 0.5

        # Fractional Kelly Criterion adjustment based on verified trade history
        kelly_factor = 1.0
        if apply_kelly:
            trades = self.portfolio.trade_history
            if len(trades) >= 10:
                wins = [t["pnl"] for t in trades if t.get("pnl", 0) > 0]
                losses = [abs(t["pnl"]) for t in trades if t.get("pnl", 0) < 0]
                if wins and losses:
                    p = len(wins) / len(trades)
                    avg_win = float(np.mean(wins))
                    avg_loss = float(np.mean(losses))
                    b = avg_win / avg_loss if avg_loss > 0 else 1.5
                    q = 1.0 - p
                    full_kelly = (p * b - q) / b if b > 0 else 0.0
                    # Quarter-Kelly scaling factor bounded between 0.5 and 1.25
                    quarter_kelly = max(0.0, full_kelly * 0.25)
                    if quarter_kelly > 0:
                        kelly_factor = min(1.25, max(0.5, quarter_kelly / (self.max_risk_pct / 100.0)))
                    else:
                        kelly_factor = 0.5  # Negative expectancy -> de-risk

        effective_risk_pct = min(self.max_risk_pct, risk_pct * kelly_factor)
        risk_capital = equity * (effective_risk_pct / 100.0)

        # Risk per unit calculation with ATR volatility floor
        risk_per_unit = abs(entry_price - stop_loss_price)
        if atr and atr > 0:
            min_atr_distance = atr * 0.5
            if risk_per_unit < min_atr_distance:
                risk_per_unit = min_atr_distance

        if risk_per_unit <= 0:
            # Fallback to 1.5% price difference
            risk_per_unit = entry_price * 0.015

        units = risk_capital / risk_per_unit

        # Capital ceiling: Do not allocate more than 25% of total free cash to a single asset
        max_cost = self.portfolio.cash * 0.25
        max_units = max_cost / entry_price if entry_price > 0 else 0
        units = min(units, max_units)

        if units <= 0:
            return 0.0

        # Dynamic precision formatting based on asset price magnitude
        if entry_price >= 1000:
            return round(units, 4)
        elif entry_price >= 50:
            return round(units, 3)
        elif entry_price >= 1.0:
            return round(units, 2)
        elif entry_price >= 0.01:
            return round(units, 1)
        else:
            return round(units, 0)

    def calculate_sl_tp(self, side: str, entry_price: float, atr: float) -> Tuple[float, list]:
        """
        Calculates dynamic Stop-Loss and Multi-tier Take-Profit targets.
        - Stop Loss = Entry - 1.5 * ATR (for BUY)
        - TP1 (1:1.5 RR): Entry + 2.25 * ATR
        - TP2 (1:2.5 RR): Entry + 3.75 * ATR
        - TP3 (1:4.0 RR): Entry + 6.00 * ATR
        Strictly enforces positive price floors on all targets.
        """
        if atr <= 0 or atr is None:
            atr = entry_price * 0.012  # Fallback: 1.2% volatility

        sl_distance = 1.5 * atr
        price_decimals = 4 if entry_price > 10 else 6
        min_price_floor = round(entry_price * 0.001, price_decimals)

        if side == "BUY":
            sl = round(entry_price - sl_distance, price_decimals)
            tp1 = round(entry_price + (sl_distance * 1.5), price_decimals)
            tp2 = round(entry_price + (sl_distance * 2.5), price_decimals)
            tp3 = round(entry_price + (sl_distance * 4.0), price_decimals)
            sl = max(sl, min_price_floor)
        else: # SELL / SHORT
            sl = round(entry_price + sl_distance, price_decimals)
            tp1 = round(entry_price - (sl_distance * 1.5), price_decimals)
            tp2 = round(entry_price - (sl_distance * 2.5), price_decimals)
            tp3 = round(entry_price - (sl_distance * 4.0), price_decimals)
            tp1 = max(tp1, min_price_floor)
            tp2 = max(tp2, min_price_floor)
            tp3 = max(tp3, min_price_floor)

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

    def run_monte_carlo_simulation(
        self, 
        trade_pnls: Optional[List[float]] = None, 
        num_simulations: int = 1000, 
        trade_count: int = 100,
        initial_capital: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Runs Monte Carlo profit probability simulations directly from RiskEngine.
        Extracts verified historical trade returns or applies synthetic institutional bootstrap.
        Computes path-dependent risk of ruin, confidence intervals, VaR, and probability of profit.
        """
        if initial_capital is None:
            initial_capital = self.portfolio.equity if self.portfolio.equity > 0 else 10000.0

        if trade_pnls is None:
            pnls = [t.get("pnl", 0.0) for t in self.portfolio.trade_history if "pnl" in t]
            trade_pnls = pnls if len(pnls) >= 5 else None

        from backtester.monte_carlo import MonteCarloSimulator
        simulation_results = MonteCarloSimulator.run_simulation(
            trade_pnls=trade_pnls,
            initial_capital=initial_capital,
            num_simulations=num_simulations,
            trade_count=trade_count
        )

        logger.info(
            f"Monte Carlo Simulation ({num_simulations} runs): "
            f"Profit Probability = {simulation_results['probability_of_profit_pct']}%, "
            f"Expected Median Equity = ${simulation_results['expected_median_equity']}, "
            f"Worst 5th Percentile Drawdown = {simulation_results['worst_95th_percentile_drawdown_pct']}%, "
            f"Path Risk of Ruin = {simulation_results['path_dependent_risk_of_ruin_pct']}%"
        )
        return simulation_results

    def calculate_var_metrics(self) -> Dict[str, Any]:
        """Calculates 1-Day 95% and 99% Parametric / Historical Value-at-Risk and CVaR."""
        from risk.var_stress_test import PortfolioStressTester
        pnls = [t.get("pnl", 0.0) for t in self.portfolio.trade_history if "pnl" in t]
        return PortfolioStressTester.calculate_var_metrics(
            portfolio_equity=self.portfolio.equity,
            trade_pnls=pnls
        )

    def simulate_black_swan_stress(self) -> List[Dict[str, Any]]:
        """Simulates extreme macro shock stress tests against active positions."""
        from risk.var_stress_test import PortfolioStressTester
        return PortfolioStressTester.simulate_black_swan_scenarios(
            portfolio_equity=self.portfolio.equity,
            open_positions=list(self.portfolio.positions.values())
        )

    def emergency_liquidate_all_positions(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Emergency de-risking: closes all open positions immediately upon critical circuit breaker breach.
        """
        closed_records = []
        for symbol in list(self.portfolio.positions.keys()):
            price = current_prices.get(symbol, self.portfolio.positions[symbol]["entry_price"])
            record = self.portfolio.close_position(symbol, price, exit_reason="EMERGENCY_CIRCUIT_BREAKER_LIQUIDATION")
            if record:
                closed_records.append(record)
        logger.warning(f"Emergency liquidated {len(closed_records)} positions due to risk breach.")
        return closed_records

    def generate_risk_audit_report(self) -> Dict[str, Any]:
        """Generates a complete, Wall Street audit summary report of portfolio risk metrics."""
        summary = self.portfolio.get_summary()
        cb_status = self.get_circuit_breaker_status()
        var_metrics = self.calculate_var_metrics()
        mc_results = self.run_monte_carlo_simulation(num_simulations=500, trade_count=50)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "account_health": {
                "equity": summary.get("equity", 0.0),
                "cash": summary.get("cash", 0.0),
                "daily_drawdown_pct": summary.get("daily_drawdown_pct", 0.0),
                "max_drawdown_pct": summary.get("max_drawdown_pct", 0.0),
                "consecutive_losses": summary.get("consecutive_losses", 0),
                "open_positions_count": summary.get("open_positions_count", 0),
            },
            "circuit_breaker": cb_status,
            "value_at_risk": var_metrics,
            "monte_carlo_simulation": mc_results,
            "risk_verdict": "SAFE_PRUDENT" if not cb_status["is_circuit_broken"] else "CIRCUIT_BREAKER_TRIGGERED"
        }
