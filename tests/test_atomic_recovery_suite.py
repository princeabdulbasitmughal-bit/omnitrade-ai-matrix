"""
================================================================================
OMNITRADE AI MATRIX — ATOMIC WRITES, CORRUPTION RESISTANCE & RECOVERY TEST SUITE
================================================================================
Validates:
1. Atomic write integrity (no partial writes, fsync sync, .bak maintenance).
2. Resistance against 0-byte truncation, partial writes, and syntax corruption.
3. Automatic self-healing of portfolio and loop states from backup (.bak).
4. Instant state recovery (<50ms) upon simulated daemon crashes and re-spawns.
================================================================================
"""
import os
import sys
import time
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.atomic_storage import atomic_write_json, atomic_read_json
from core.portfolio import Portfolio


class TestOmniTradeAtomicAndRecovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="omnitrade_test_"))
        self.state_file = self.test_dir / "test_portfolio.json"

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_01_atomic_write_creates_valid_file_and_backup(self):
        """Test that atomic_write_json creates valid file and subsequent write creates .bak"""
        sample_data_v1 = {"version": 1, "cash": 10000.0, "trades": [{"id": 1, "pnl": 50.0}]}
        sample_data_v2 = {"version": 2, "cash": 10050.0, "trades": [{"id": 1, "pnl": 50.0}, {"id": 2, "pnl": 75.0}]}

        # First write
        success = atomic_write_json(self.state_file, sample_data_v1, backup=True)
        self.assertTrue(success)
        self.assertTrue(self.state_file.exists())
        self.assertGreater(self.state_file.stat().st_size, 0)

        # Second write should create .bak containing v1
        success = atomic_write_json(self.state_file, sample_data_v2, backup=True)
        self.assertTrue(success)

        bak_file = self.state_file.with_suffix(".json.bak")
        self.assertTrue(bak_file.exists(), ".bak backup file must be created")

        # Verify target is v2 and .bak is v1
        data_v2, _ = atomic_read_json(self.state_file)
        data_v1, _ = atomic_read_json(bak_file)
        self.assertEqual(data_v2["version"], 2)
        self.assertEqual(data_v1["version"], 1)
        self.assertEqual(data_v2["cash"], 10050.0)
        self.assertEqual(data_v1["cash"], 10000.0)

    def test_02_corruption_resistance_truncated_json(self):
        """Test that truncated/malformed JSON in primary file triggers auto-healing from .bak"""
        golden_data = {
            "cash": 8991.09,
            "equity": 8991.09,
            "peak_equity": 11741.98,
            "positions": {"BTC/USDT": {"amount": 0.05, "entry_price": 60000.0}},
            "trade_history": [{"id": "t1", "pnl": 230.5, "symbol": "BTC/USDT"}]
        }
        # 1. Establish valid state and backup
        atomic_write_json(self.state_file, golden_data, backup=True)
        # Update once to generate valid .bak
        golden_data["cash"] = 9200.00
        atomic_write_json(self.state_file, golden_data, backup=True)

        # 2. Inject intentional corruption into primary file (truncated JSON)
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write('{"cash": 9200.00, "equity": 9200.00, "positions": {"BTC/USDT": {"amount": 0.05, "entry_p')

        # 3. Read using atomic_read_json with auto-heal
        recovered_data, was_healed = atomic_read_json(self.state_file, auto_heal_from_backup=True)

        self.assertTrue(was_healed, "Should flag that state was healed from backup")
        self.assertIsNotNone(recovered_data)
        self.assertEqual(recovered_data["peak_equity"], 11741.98)
        self.assertIn("BTC/USDT", recovered_data["positions"])
        self.assertEqual(len(recovered_data["trade_history"]), 1)

        # 4. Verify primary file itself was auto-repaired on disk
        with open(self.state_file, "r", encoding="utf-8") as f:
            repaired_on_disk = json.load(f)
        self.assertEqual(repaired_on_disk["peak_equity"], 11741.98)

    def test_03_corruption_resistance_zero_byte_file(self):
        """Test that 0-byte file (crash mid-write simulation) is instantly healed from .bak"""
        state = {"cash": 12500.0, "daily_date": "2026-10-04", "trade_history": [{"id": 1}]}
        atomic_write_json(self.state_file, state, backup=True)
        # Second write to create .bak
        state["cash"] = 12600.0
        atomic_write_json(self.state_file, state, backup=True)

        # Simulate 0-byte file resulting from hard process termination
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write("")

        self.assertEqual(self.state_file.stat().st_size, 0)

        # Portfolio load should heal automatically
        port = Portfolio(storage_path=self.state_file)
        self.assertEqual(port.cash, 12500.0)
        self.assertEqual(len(port.trade_history), 1)

        # Verify disk state has been restored to valid non-zero JSON
        self.assertGreater(self.state_file.stat().st_size, 0)

    def test_04_instant_state_recovery_upon_daemon_respawn(self):
        """Test state preservation across multiple rapid portfolio instances (simulating daemon crashes/restarts)"""
        # Step 1: Initial daemon opens trades and updates equity
        p1 = Portfolio(storage_path=self.state_file)
        p1.open_position("XAUUSD", "BUY", 0.5, 2400.0, sl=2380.0, tp=[2450.0], reason="SMC Bullish")
        p1.open_position("BTC/USDT", "BUY", 0.1, 65000.0, sl=63000.0, tp=[70000.0], reason="RSI Oversold")
        p1.close_position("XAUUSD", exit_price=2430.0, exit_reason="TAKE_PROFIT_1")

        cash_before_kill = p1.cash
        equity_before_kill = p1.equity
        positions_before_kill = len(p1.positions)
        trades_before_kill = len(p1.trade_history)

        self.assertEqual(positions_before_kill, 1)  # BTC/USDT still open
        self.assertEqual(trades_before_kill, 1)     # XAUUSD closed

        # Step 2: Sudden termination / daemon crash simulation (delete in-memory object)
        del p1

        # Step 3: Daemon re-spawns — measure recovery latency
        t0 = time.perf_counter()
        p2 = Portfolio(storage_path=self.state_file)
        recovery_duration_ms = (time.perf_counter() - t0) * 1000

        # Step 4: Validate instant recovery (<50ms) and exact state persistence
        self.assertLess(recovery_duration_ms, 50.0, f"Recovery latency {recovery_duration_ms:.2f}ms exceeds 50ms")
        self.assertAlmostEqual(p2.cash, cash_before_kill, places=2)
        self.assertAlmostEqual(p2.equity, equity_before_kill, places=2)
        self.assertEqual(len(p2.positions), 1)
        self.assertIn("BTC/USDT", p2.positions)
        self.assertEqual(len(p2.trade_history), 1)
        self.assertEqual(p2.trade_history[0]["symbol"], "XAUUSD")
        self.assertEqual(p2.trade_history[0]["exit_reason"], "TAKE_PROFIT_1")
        print(f"\n[PASS] OmniTrade instant state recovery latency: {recovery_duration_ms:.3f} ms")


if __name__ == "__main__":
    unittest.main()
