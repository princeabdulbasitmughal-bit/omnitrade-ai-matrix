import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.max_compute_swarm import MaxComputeSwarmRunner

def run():
    runner = MaxComputeSwarmRunner()
    res = runner.run_full_99pct_matrix_burst(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XAU/USD'])
    print("==================================================")
    print("🔥 99% COMPUTE SWARM MATRIX BURST VERIFICATION")
    print(f"Status: {res['status']}")
    print(f"Total Parallel Matrix Latency: {res['matrix_burst_latency_ms']} ms")
    print(f"GPU Hardware Allocation: {res['gpu_utilization_target']}")
    print(f"All Models Fired Concurrently: {', '.join(res['models_engaged'])}")
    print(f"Symbols Evaluated: {res['symbols_evaluated']}")
    print(f"Cross-Exchange Arbitrage Spread: ${res['arbitrage_spread_usd']:.2f}")
    print("==================================================")

if __name__ == "__main__":
    run()
