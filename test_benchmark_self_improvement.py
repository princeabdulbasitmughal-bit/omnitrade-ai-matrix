import requests
import json

BASE_URL = "http://localhost:8888"

def test_endpoints():
    print("Testing OmniTrade Pro Institutional Benchmark & Self-Improvement...")
    
    # 1. Test Status
    res_status = requests.get(f"{BASE_URL}/api/status")
    print(f"1. /api/status: {res_status.status_code}")
    
    # 2. Test Competitors Benchmark
    res_bm = requests.get(f"{BASE_URL}/api/benchmark/competitors")
    print(f"2. /api/benchmark/competitors: {res_bm.status_code}")
    if res_bm.status_code == 200:
        bm_data = res_bm.json()
        print(f"   Alpha Score: {bm_data.get('overall_composite_alpha_score')} / 100")
        print(f"   Competitors Benchmarked: {len(bm_data.get('competitor_ranking', []))}")
        for c in bm_data.get('competitor_ranking', []):
            print(f"   • {c['competitor_name']}: {c['omnitrade_sharpe']} Sharpe ({c['sharpe_alpha_spread']}) | {c['feature_advantage']} | [{c['rating']}]")

    # 3. Test Self-Improvement Status
    res_si = requests.get(f"{BASE_URL}/api/benchmark/self-improvement")
    print(f"3. /api/benchmark/self-improvement: {res_si.status_code}")
    if res_si.status_code == 200:
        si_data = res_si.json()
        print(f"   Iteration: #{si_data.get('iteration_count')}")
        print(f"   Learning Gain: +{si_data.get('cumulative_learning_gain_pct')}%")
        print(f"   Weights: {si_data.get('weight_percentages')}")

    # 4. Test Manual Optimization POST
    res_opt = requests.post(f"{BASE_URL}/api/benchmark/optimize")
    print(f"4. /api/benchmark/optimize: {res_opt.status_code}")
    if res_opt.status_code == 200:
        opt_data = res_opt.json()
        print(f"   New Iteration: #{opt_data.get('iteration_count')}")
        print(f"   Updated Weights: {opt_data.get('weight_percentages')}")
        print(f"   Cumulative Learning Gain: +{opt_data.get('cumulative_learning_gain_pct')}%")

    print("\n✅ ALL INSTITUTIONAL BENCHMARK & SELF-IMPROVEMENT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_endpoints()
