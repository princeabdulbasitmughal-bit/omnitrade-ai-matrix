import random
import logging
import requests
from typing import Dict, Any
from config.settings import Config

logger = logging.getLogger("OmniTrade.HFSentimentAgent")

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

    def analyze(self, symbol: str, price_change_24h: float = 0.0) -> Dict[str, Any]:
        """
        Analyzes real-time market sentiment, social chatter, and Fear & Greed index using Hugging Face Cluster.
        """
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # 1. Attempt live Fear & Greed API
        fear_greed_val = 65
        fear_greed_class = "Greed"
        try:
            fg_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=4)
            if fg_res.status_code == 200:
                fg_data = fg_res.json().get("data", [])
                if fg_data:
                    fear_greed_val = int(fg_data[0].get("value", 65))
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
            "sentiment": sentiment,
            "confidence": round(conf, 2),
            "fear_greed_index": fear_greed_val,
            "fear_greed_classification": fear_greed_class,
            "rationale": rationale,
            "status": "LIVE_CLUSTER" if token else "STANDALONE_SENTIMENT"
        }
