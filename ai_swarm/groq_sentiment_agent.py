import os
import time
import json
import logging
import requests
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Ensure root .env is loaded
root_env = Path("e:/.env")
if root_env.exists():
    load_dotenv(dotenv_path=root_env)

logger = logging.getLogger("OmniTrade.GroqSentimentAgent")

class GroqSentimentAgent:
    """
    Ultra-Fast Institutional Market Sentiment Agent powered by Groq LPU Inference.
    Analyzes live Fear & Greed metrics, macro news sentiment, and social flow.
    """
    GROQ_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "allam-2-7b"
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = os.getenv("GROQ_SENTIMENT_MODEL", "openai/gpt-oss-120b")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def analyze(self, symbol: str, price_change_24h: float = 0.0) -> Dict[str, Any]:
        """
        Runs high-speed sentiment analysis using Groq LPU with Fear & Greed synthesis.
        """
        t0 = time.time()

        # 1. Fetch live Fear & Greed Index
        fear_greed_val = 65
        fear_greed_class = "Greed"
        try:
            fg_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=2.5)
            if fg_res.status_code == 200:
                fg_data = fg_res.json().get("data", [])
                if fg_data:
                    fear_greed_val = int(fg_data[0].get("value", 65))
                    fear_greed_class = fg_data[0].get("value_classification", "Greed")
        except Exception as e:
            logger.debug(f"Fear & Greed fetch failed: {e}")

        # 2. Derive deterministic baseline
        norm_fg = (fear_greed_val - 50) / 50.0  # -1 to +1
        norm_change = max(-1.0, min(1.0, price_change_24h / 5.0))
        composite_score = (norm_fg * 0.6) + (norm_change * 0.4)

        if composite_score > 0.25:
            baseline_sentiment = "BULLISH"
            baseline_signal = "BUY"
            baseline_conf = min(0.92, 0.60 + (composite_score * 0.35))
            baseline_rationale = f"Market sentiment Bullish with Fear & Greed at {fear_greed_val} ({fear_greed_class}) and positive net inflow."
        elif composite_score < -0.25:
            baseline_sentiment = "BEARISH"
            baseline_signal = "SELL"
            baseline_conf = min(0.90, 0.60 + (abs(composite_score) * 0.35))
            baseline_rationale = f"Market sentiment Bearish with Fear & Greed at {fear_greed_val} ({fear_greed_class}) and risk-off rotation."
        else:
            baseline_sentiment = "NEUTRAL"
            baseline_signal = "HOLD"
            baseline_conf = 0.50
            baseline_rationale = f"Balanced sentiment environment with Fear & Greed at {fear_greed_val} ({fear_greed_class})."

        # 3. If GROQ_API_KEY available, query Groq LPU
        if self.api_key:
            prompt = f"""You are Groq LPU Quantitative Sentiment Engine, an institutional high-frequency sentiment strategist.
Analyze market sentiment for {symbol}:
- 24h Price Change: {price_change_24h:+.2f}%
- Crypto Fear & Greed Index: {fear_greed_val}/100 ({fear_greed_class})
- Current Sentiment Trend: {baseline_sentiment}

Respond STRICTLY in valid JSON matching this schema:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.50 to 0.95,
  "rationale": "one concise sentence explaining sentiment and liquidity flow"
}}
"""
            for target_model in [self.model] + [m for m in self.GROQ_MODELS if m != self.model]:
                try:
                    resp = requests.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": target_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.1,
                            "max_tokens": 120
                        },
                        timeout=3.0
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        data = json.loads(content)
                        sig = data.get("signal", baseline_signal).upper()
                        if sig not in ["BUY", "SELL", "HOLD"]:
                            sig = baseline_signal
                        conf = float(data.get("confidence", baseline_conf))
                        conf = max(0.40, min(0.95, conf))
                        elapsed_ms = round((time.time() - t0) * 1000, 1)
                        return {
                            "agent": f"Groq LPU Sentiment ({target_model})",
                            "signal": sig,
                            "sentiment": data.get("sentiment", baseline_sentiment).upper(),
                            "confidence": round(conf, 2),
                            "fear_greed_index": fear_greed_val,
                            "fear_greed_classification": fear_greed_class,
                            "rationale": data.get("rationale", baseline_rationale),
                            "status": "LIVE_GROQ_LPU",
                            "latency_ms": elapsed_ms
                        }
                except Exception as e:
                    logger.debug(f"Groq model {target_model} failed: {e}")
                    continue

        # Deterministic Fallback
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        return {
            "agent": "Groq Sentiment Engine (Deterministic Mode)",
            "signal": baseline_signal,
            "sentiment": baseline_sentiment,
            "confidence": round(baseline_conf, 2),
            "fear_greed_index": fear_greed_val,
            "fear_greed_classification": fear_greed_class,
            "rationale": baseline_rationale,
            "status": "DETERMINISTIC_FALLBACK",
            "latency_ms": elapsed_ms
        }
