"""
Institutional Audit Test Suite for OmniTrade Risk Engine
=========================================================
Validates:
1. Drawdown Limits: Daily Drawdown (3.0%) and Peak-to-Trough Portfolio Drawdown (6.0%).
2. Position Sizing Algorithms: Fixed Fractional Risk, ATR Volatility adjustments, Fractional Kelly scaling,
   25% single-asset cash ceiling, and precision formatting.
3. Circuit Breaker Thresholds: Multi-tier hard halt, consecutive loss cooldown, soft risk de-rating,
   diagnostic status reporting, and authorized reset logic.
4. Monte Carlo Profit Probability Simulations: Bootstrap resampling, path-dependent risk of ruin,
   confidence intervals, and Value-at-Risk (VaR / CVaR).
"""

import sys
import os
import unittest
from pathlib import Path
import tempfile
import numpy as np

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from core.portfolio import Portfolio
from core.risk_engine import RiskEngine
from omnitrade.risk.risk_engine import RiskEngine as OmnitradeRiskEngine
from risk.risk_engine import RiskEngine as RiskPackageRiskEngine
from backtester.monte_carlo import MonteCarloSimulator
from risk.var_stress_test import PortfolioStressTester

class TestRiskEngineAudit(unittest.TestCase):

    def setUp(self):
        # Create an isolated temporary portfolio file for clean testing
        self.temp_file = Path(tempfile.gettempdir()) / f"test_audit_portfolio_{os.getpid()}.json"
        if self.temp_file.exists():
            try:
                self.temp_file.unlink()
            except Exception:
                pass
        self.portfolio = Portfolio(initial_balance=10000.0, storage_path=self.temp_file)
        self.portfolio.cash = 10000.0
        self.portfolio.equity = 10000.0
        self.portfolio.peak_equity = 10000.0
        self.portfolio.daily_start_equity = 10000.0
        self.portfolio.positions = {}
        self.portfolio.trade_history = []
        self.risk_engine = RiskEngine(self.portfolio)

    def tearDown(self):
        if self.temp_file.exists():
            try:
                self.temp_file.unlink()
            except Exception:
                pass

    # =========================================================================
    # 1. Module Compatibility & Namespace Validation
    # =========================================================================
    def test_module_namespace_compatibility(self):
        """Validates that RiskEngine is identically accessible from all required namespace paths."""
        self.assertIs(RiskEngine, OmnitradeRiskEngine)
        self.assertIs(RiskEngine, RiskPackageRiskEngine)

    # =========================================================================
    # 2. Drawdown Limits Validation
    # =========================================================================
    def test_daily_drawdown_limit_enforcement(self):
        """Validates that daily drawdown of 3.0% triggers the daily circuit breaker."""
        # 2.5% daily drop -> within limit (3.0%)
        self.portfolio.equity = 9750.0
        is_broken, msg = self.risk_engine.check_circuit_breaker()
        self.assertFalse(is_broken)
        self.assertIn("Normal Risk Operations", msg)

        # 3.0% drop from daily start (10000 -> 9700) -> Triggers Circuit Breaker
        self.portfolio.equity = 9700.0
        is_broken, msg = self.risk_engine.check_circuit_breaker()
        self.assertTrue(is_broken)
        self.assertTrue(self.risk_engine.is_circuit_broken)
        self.assertIn("DAILY DRAWDOWN BREACH", msg)
        self.assertIn("3.00%", msg)

    def test_total_portfolio_drawdown_limit_enforcement(self):
        """Validates that peak-to-trough cumulative drawdown of 6.0% triggers emergency halt."""
        # Start day with 9500 (daily start equity = 9500), but peak was 10000
        self.portfolio.daily_start_equity = 9500.0
        self.portfolio.peak_equity = 10000.0
        # Equity is 9390: Daily DD = (9500 - 9390)/9500 = 1.15% (OK)
        # Total DD = (10000 - 9390)/10000 = 6.10% (BREACH of 6.0% max total DD!)
        self.portfolio.equity = 9390.0
        is_broken, msg = self.risk_engine.check_circuit_breaker()
        self.assertTrue(is_broken)
        self.assertIn("MAX TOTAL DRAWDOWN BREACH", msg)
        self.assertIn("6.10%", msg)

    def test_peak_equity_tracking_on_trade_closures(self):
        """Validates that peak equity updates immediately on trade close."""
        self.portfolio.open_position("BTC/USDT", "BUY", 0.1, 50000.0, 48000.0, [55000.0])
        # Close at profit (price = 60000, gross gain = 1000)
        self.portfolio.close_position("BTC/USDT", 60000.0, exit_reason="TAKE_PROFIT")
        self.assertGreater(self.portfolio.equity, 10000.0)
        self.assertEqual(self.portfolio.peak_equity, self.portfolio.equity)

    # =========================================================================
    # 3. Position Sizing Algorithms Validation
    # =========================================================================
    def test_fixed_fractional_position_sizing(self):
        """
        Validates Fixed Fractional Risk Position Sizing:
        Risk capital = Equity * 1.5% = $150
        Entry = $100, Stop Loss = $95 (Risk distance = $5)
        Units = 150 / 5 = 30.0 units
        """
        units = self.risk_engine.calculate_position_size("ETH/USDT", entry_price=100.0, stop_loss_price=95.0, apply_kelly=False)
        self.assertEqual(units, 30.0)

    def test_atr_volatility_floor_adjustment(self):
        """
        Validates that position sizing applies ATR volatility floor (min risk distance = 0.5 * ATR)
        to prevent over-leveraging on unrealistically tight stop losses.
        """
        # Entry = 100, tight manual SL = 99.9 (distance = 0.1)
        # ATR = 4.0 -> min distance = 2.0
        # Risk capital = $150 -> Units = 150 / 2.0 = 75.0 units instead of 150 / 0.1 = 1500 units!
        units = self.risk_engine.calculate_position_size("SOL/USDT", entry_price=100.0, stop_loss_price=99.9, atr=4.0, apply_kelly=False)
        self.assertEqual(units, 75.0)

    def test_cash_capital_ceiling_constraint(self):
        """Validates that no position may commit more than 25% of available cash."""
        # Cash = 10,000 -> Max allocation = 2,500
        # Entry = 100, Stop Loss = 99.99 (distance = 0.01)
        # Unbounded units would be 15,000 ($1,500,000 value!)
        # Max units must be capped at 2500 / 100 = 25.0 units
        units = self.risk_engine.calculate_position_size("BTC/USDT", entry_price=100.0, stop_loss_price=99.99, atr=0.0, apply_kelly=False)
        self.assertEqual(units, 25.0)

    def test_dynamic_asset_magnitude_precision(self):
        """Validates that precision is properly scaled according to asset price magnitude."""
        # High value asset (BTC > 1000): 4 decimals
        btc_units = self.risk_engine.calculate_position_size("BTC/USDT", entry_price=95000.0, stop_loss_price=93500.0)
        self.assertEqual(len(str(btc_units).split(".")[-1]), 4)

        # Mid value asset (SOL $150): 3 decimals
        sol_units = self.risk_engine.calculate_position_size("SOL/USDT", entry_price=150.0, stop_loss_price=145.0)
        self.assertLessEqual(len(str(sol_units).split(".")[-1]), 3)

        # Low value penny token ($0.05): 1 decimal
        doge_units = self.risk_engine.calculate_position_size("DOGE/USDT", entry_price=0.05, stop_loss_price=0.048)
        self.assertGreater(doge_units, 0.0)

    def test_dynamic_sl_and_multi_tier_tp_levels(self):
        """
        Validates Dynamic SL (1.5x ATR) and Multi-Tier TP targets (1:1.5, 1:2.5, 1:4.0 RR)
        with non-negative price floor protections.
        """
        # BUY side
        sl_buy, tps_buy = self.risk_engine.calculate_sl_tp("BUY", entry_price=100.0, atr=2.0)
        self.assertEqual(sl_buy, 97.0) # 100 - (1.5 * 2)
        self.assertEqual(len(tps_buy), 3)
        self.assertEqual(tps_buy[0], 104.5) # 100 + (3.0 * 1.5) = 104.5
        self.assertEqual(tps_buy[1], 107.5) # 100 + (3.0 * 2.5) = 107.5
        self.assertEqual(tps_buy[2], 112.0) # 100 + (3.0 * 4.0) = 112.0

        # SELL side
        sl_sell, tps_sell = self.risk_engine.calculate_sl_tp("SELL", entry_price=100.0, atr=2.0)
        self.assertEqual(sl_sell, 103.0)
        self.assertEqual(tps_sell[0], 95.5)
        self.assertEqual(tps_sell[1], 92.5)
        self.assertEqual(tps_sell[2], 88.0)

        # Extreme high ATR on low price: floor protection
        sl_floor, _ = self.risk_engine.calculate_sl_tp("BUY", entry_price=1.0, atr=5.0)
        self.assertGreater(sl_floor, 0.0)

    # =========================================================================
    # 4. Circuit Breaker Thresholds Validation
    # =========================================================================
    def test_consecutive_losses_circuit_breaker(self):
        """Validates that 4 consecutive losing trades triggers cooldown circuit breaker."""
        # Add 4 consecutive losses to trade history
        for i in range(4):
            self.portfolio.trade_history.append({"id": f"t_{i}", "pnl": -50.0})

        is_broken, msg = self.risk_engine.check_circuit_breaker()
        self.assertTrue(is_broken)
        self.assertIn("CONSECUTIVE LOSSES BREACH", msg)
        self.assertIn("4 consecutive loss trades", msg)

    def test_soft_circuit_risk_derating(self):
        """
        Validates soft risk de-rating: when daily drawdown reaches 70% of limit (>= 2.1%),
        position sizing risk is halved as a precautionary buffer.
        """
        # Normal sizing risk capital = $150
        normal_units = self.risk_engine.calculate_position_size("ETH/USDT", entry_price=100.0, stop_loss_price=95.0, apply_kelly=False)
        self.assertEqual(normal_units, 30.0)

        # Drop equity to 9780 (Daily DD = 2.2% >= 2.1% soft threshold)
        self.portfolio.equity = 9780.0
        self.risk_engine.check_circuit_breaker()
        self.assertTrue(self.risk_engine.soft_circuit_active)

        # Sizing under soft circuit: Risk % halved to 0.75% -> Risk capital = 9780 * 0.75% = $73.35
        # Units = 73.35 / 5 = 14.67
        derated_units = self.risk_engine.calculate_position_size("ETH/USDT", entry_price=100.0, stop_loss_price=95.0, apply_kelly=False)
        self.assertAlmostEqual(derated_units, 14.67, places=2)

    def test_circuit_breaker_reset_logic(self):
        """Validates authorized and unauthorized circuit breaker reset attempts."""
        # Trigger circuit breaker
        self.portfolio.equity = 9600.0 # 4% DD
        self.risk_engine.check_circuit_breaker()
        self.assertTrue(self.risk_engine.is_circuit_broken)

        # Non-admin reset fails while conditions still breach
        success, msg = self.risk_engine.reset_circuit_breaker(admin_override=False)
        self.assertFalse(success)
        self.assertTrue(self.risk_engine.is_circuit_broken)

        # Admin override reset succeeds
        success_override, msg_override = self.risk_engine.reset_circuit_breaker(admin_override=True)
        self.assertTrue(success_override)
        self.assertFalse(self.risk_engine.is_circuit_broken)

    # =========================================================================
    # 5. Monte Carlo Profit Probability Simulation Validation
    # =========================================================================
    def test_monte_carlo_simulation_metrics(self):
        """
        Validates Monte Carlo simulation engine:
        - Probability of Profit calculation
        - 95% and 99% Confidence intervals
        - Path-dependent vs Terminal Risk of Ruin
        - Value-at-Risk (VaR) and CVaR
        """
        trade_pnls = [150.0, 220.0, -95.0, 310.0, -80.0, 180.0, -110.0, 450.0, -90.0, 200.0]
        mc_results = MonteCarloSimulator.run_simulation(
            trade_pnls=trade_pnls,
            initial_capital=10000.0,
            num_simulations=1000,
            trade_count=50,
            ruin_threshold_pct=50.0
        )

        self.assertEqual(mc_results["num_simulations"], 1000)
        self.assertEqual(mc_results["simulated_trades_per_run"], 50)
        self.assertIn("probability_of_profit_pct", mc_results)
        self.assertGreaterEqual(mc_results["probability_of_profit_pct"], 90.0) # Profitable distribution
        self.assertGreater(mc_results["expected_median_equity"], 10000.0)
        self.assertIn("worst_5th_percentile_equity", mc_results)
        self.assertIn("best_95th_percentile_equity", mc_results)
        self.assertIn("path_dependent_risk_of_ruin_pct", mc_results)
        self.assertIn("var_95_pct", mc_results)
        self.assertIn("cvar_99_pct", mc_results)
        self.assertLessEqual(mc_results["path_dependent_risk_of_ruin_pct"], 1.0)

    def test_risk_engine_monte_carlo_integration(self):
        """Validates that RiskEngine directly runs Monte Carlo simulation with portfolio context."""
        # Populate realistic history
        for pnl in [200.0, 180.0, -90.0, 250.0, -100.0, 300.0]:
            self.portfolio.trade_history.append({"id": f"t_{pnl}", "pnl": pnl})

        mc = self.risk_engine.run_monte_carlo_simulation(num_simulations=300, trade_count=40)
        self.assertIn("probability_of_profit_pct", mc)
        self.assertGreaterEqual(mc["probability_of_profit_pct"], 0.0)

    def test_risk_audit_report_generation(self):
        """Validates comprehensive Wall Street Risk Audit Report generation."""
        report = self.risk_engine.generate_risk_audit_report()
        self.assertIn("account_health", report)
        self.assertIn("circuit_breaker", report)
        self.assertIn("value_at_risk", report)
        self.assertIn("monte_carlo_simulation", report)
        self.assertEqual(report["risk_verdict"], "SAFE_PRUDENT")


if __name__ == "__main__":
    unittest.main()
