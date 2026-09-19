import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategies.ml_predictor import MLAlphaPredictor
from core.market_data import MarketDataProvider

def benchmark():
    md = MarketDataProvider()
    df = md.fetch_ohlcv('BTC/USDT', limit=80)

    predictor = MLAlphaPredictor()
    
    # Measure latency across 5 iterations
    latencies = []
    res = None
    for _ in range(5):
        t0 = time.perf_counter()
        res = predictor.predict_next_candle(df)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    avg_lat = sum(latencies) / len(latencies)

    print("==================================================")
    print(f"🚀 ULTRA-EFFICIENT ENSEMBLE PREDICTOR BENCHMARK")
    print(f"Average Inference Latency: {avg_lat:.2f} ms")
    print("--------------------------------------------------")
    print(f"Ensemble Prediction: {res['prediction']} ({res['confidence']*100:.1f}% Confidence)")
    print(f"Bullish Probability: {res['bullish_prob']*100:.1f}% | Bearish: {res['bearish_prob']*100:.1f}%")
    print(f"Statistical Regime: {res['regime']} (Hurst Exponent: {res['hurst_exponent']})")
    print(f"Expected 3-Candle Alpha Yield: {res['expected_return_3bar_pct']:+.3f}%")
    print("\nTriple-Model Breakdown:")
    for model_name, prob in res['model_breakdown'].items():
        print(f"  • {model_name}: {prob*100:.1f}% Bullish")
    print("\nTop Predictive Features by Importance:")
    for feat, imp in res['top_features'].items():
        print(f"  • {feat}: {imp*100:.1f}%")
    print("==================================================")

if __name__ == "__main__":
    benchmark()
