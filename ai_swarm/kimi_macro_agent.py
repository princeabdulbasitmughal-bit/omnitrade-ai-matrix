import json
import logging
import requests
from typing import Dict, Any
from config.settings import Config

logger = logging.getLogger("OmniTrade.KimiMacroAgent")

class KimiMacroAgent:
    def __init__(self):
        self.model = Config.KIMI_MODEL
        self.hermes_model = Config.HERMES_MODEL
        self.base_url = Config.OLLAMA_BASE_URL

    def analyze(self, symbol: str, tech_summary: Dict[str, Any], market_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Evaluates Macroeconomic context, market regime, and multi-asset liquidity dynamics.
        """
        prompt = f"""You are Kimi Macro Reasoning Engine, an institutional global macro strategist.
Analyze market context for {symbol}:
- Price: {tech_summary.get('close')}
- 24h Change: {market_state.get('change_24h', 0) if market_state else 0}%
- EMA 50 vs EMA 200 Trend: {'Bullish' if tech_summary.get('ema_50', 0) > tech_summary.get('ema_200', 0) else 'Bearish'}
- VWAP: {tech_summary.get('vwap')}

Respond STRICTLY in JSON:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "market_regime": "TRENDING_BULL" | "TRENDING_BEAR" | "RANGING" | "LIQUIDITY_CRISIS",
  "macro_thesis": "2-sentence macro reasoning"
}}
"""
        # Try Ollama model (kimi or hermes)
        for target_model in [self.model, self.hermes_model, Config.FAST_CHAT_MODEL]:
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": target_model, "prompt": prompt, "format": "json", "stream": False},
                    timeout=8
                )
                if resp.status_code == 200:
                    data = json.loads(resp.json().get("response", "{}"))
                    return {
                        "agent": f"Kimi Macro AI ({target_model})",
                        "signal": data.get("signal", "HOLD").upper(),
                        "confidence": float(data.get("confidence", 0.5)),
                        "market_regime": data.get("market_regime", "TRENDING_BULL"),
                        "rationale": data.get("macro_thesis", "Macro regime supports current trend."),
                        "status": "LIVE_GPU"
                    }
            except Exception:
                continue

        # Macro Heuristic fallback
        ema_50 = tech_summary.get("ema_50", 0)
        ema_200 = tech_summary.get("ema_200", 0)
        vwap = tech_summary.get("vwap", 0)
        close = tech_summary.get("close", 0)

        if close > vwap and ema_50 > ema_200:
            sig = "BUY"
            conf = 0.78
            regime = "TRENDING_BULL"
            thesis = "Price holding firmly above institutional VWAP with golden cross moving average structure."
        elif close < vwap and ema_50 < ema_200:
            sig = "SELL"
            conf = 0.76
            regime = "TRENDING_BEAR"
            thesis = "Sustained trading below VWAP accompanied by death-cross trend structure indicating macro distribution."
        else:
            sig = "HOLD"
            conf = 0.52
            regime = "RANGING / RE-ACCUMULATION"
            thesis = "Macro liquidity indicators show equilibrium within standard deviation boundaries."

        return {
            "agent": "Kimi K3 Macro Reasoning (Engine)",
            "signal": sig,
            "confidence": conf,
            "market_regime": regime,
            "rationale": thesis,
            "status": "DETERMINISTIC_FALLBACK"
        }
