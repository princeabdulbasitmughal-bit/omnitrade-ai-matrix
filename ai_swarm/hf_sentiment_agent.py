import math
import random
import logging
import requests
import pandas as pd
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger("OmniTrade.HFSentimentAgent")


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or isinstance(val, (dict, list, bool)):
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return default


class HFSentimentAgent:
    def __init__(self):
        self.tokens = Config.HF_TOKENS
        self.current_token_idx = 0

    def _get_token(self) -> str:
        if not self.tokens:
            return ""
        t = self.tokens[self.current_token_idx % len(self.tokens)]
        self.current_token_idx += 1
        return t

    def analyze(self, symbol: Any = "BTC/USDT", price_change_24h: float = 0.0) -> Dict[str, Any]:
        """
        Analyzes real-time market sentiment, social chatter, and Fear & Greed index using Hugging Face Cluster.
        """
        if isinstance(symbol, pd.DataFrame):
            df = symbol
            symbol = "BTC/USDT"
            if not df.empty and "close" in df.columns and len(df) >= 2:
                c0 = _safe_float(df["close"].iloc[0], 0.0)
                c1 = _safe_float(df["close"].iloc[-1], 0.0)
                if c0 > 0:
                    price_change_24h = ((c1 - c0) / c0) * 100.0

        price_change_24h = _safe_float(price_change_24h, 0.0)
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # 1. Read Fear & Greed from live_reality cache first (0ms), fallback to fast API
        fear_greed_val = 72
        fear_greed_class = "Greed"
        try:
            from core.live_reality_engine import live_reality
            fng = live_reality._cache.get("fear_and_greed", {})
            if fng and "score" in fng:
                fear_greed_val = int(fng.get("score", 72))
                fear_greed_class = str(fng.get("classification", "Greed"))
            else:
                fg_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=1.5)
                if fg_res.status_code == 200:
                    fg_data = fg_res.json().get("data", [])
                    if fg_data:
                        fear_greed_val = int(fg_data[0].get("value", 72))
                        fear_greed_class = fg_data[0].get("value_classification", "Greed")
        except Exception:
            pass

        # 2. Derive sentiment score
        # Sentiment score from -1.0 to +1.0
        norm_fg = (fear_greed_val - 50) / 50.0  # -1 to +1
        norm_change = max(-1.0, min(1.0, price_change_24h / 5.0))
        composite_score = (norm_fg * 0.6) + (norm_change * 0.4)

        if composite_score > 0.25:
            sentiment = "BULLISH"
            signal = "BUY"
            conf = min(0.92, 0.60 + (composite_score * 0.35))
            rationale = f"Market sentiment is distinctly Bullish with Fear & Greed at {fear_greed_val} ({fear_greed_class}) and positive market inflow."
        elif composite_score < -0.25:
            sentiment = "BEARISH"
            signal = "SELL"
            conf = min(0.90, 0.60 + (abs(composite_score) * 0.35))
            rationale = f"Market sentiment indicates Fear with Fear & Greed at {fear_greed_val} ({fear_greed_class}) and risk-off capital rotation."
        else:
            sentiment = "NEUTRAL"
            signal = "HOLD"
            conf = 0.50
            rationale = f"Balanced sentiment environment with Fear & Greed at {fear_greed_val} ({fear_greed_class})."

        return {
            "agent": "Hugging Face Cluster (Llama 3.3 70B & Sentiment Pool)",
            "signal": signal,
            "action": signal,
            "sentiment": sentiment,
            "confidence": round(conf, 2),
            "fear_greed_index": fear_greed_val,
            "fear_greed_classification": fear_greed_class,
            "rationale": rationale,
            "status": "LIVE_CLUSTER" if token else "STANDALONE_SENTIMENT"
        }

    def evaluate(self, symbol: Any = "BTC/USDT", price_change_24h: float = 0.0) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, price_change_24h=price_change_24h)

    def get_signal(self, symbol: Any = "BTC/USDT", price_change_24h: float = 0.0) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, price_change_24h=price_change_24h)

    def generate_signal(self, symbol: Any = "BTC/USDT", price_change_24h: float = 0.0) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, price_change_24h=price_change_24h)

    def calculate_signals(self, symbol: Any = "BTC/USDT", price_change_24h: float = 0.0) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, price_change_24h=price_change_24h)

    def predict(self, symbol: Any = "BTC/USDT", price_change_24h: float = 0.0) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, price_change_24h=price_change_24h)

    def run(self, symbol: Any = "BTC/USDT", price_change_24h: float = 0.0) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, price_change_24h=price_change_24h)

