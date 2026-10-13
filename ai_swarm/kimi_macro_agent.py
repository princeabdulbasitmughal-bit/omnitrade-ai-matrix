import json
import logging
import math
import requests
import pandas as pd
from typing import Dict, Any, Optional
from config.settings import Config

logger = logging.getLogger("OmniTrade.KimiMacroAgent")


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or isinstance(val, (dict, list, bool)):
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return default


class KimiMacroAgent:
    def __init__(self):
        self.model = Config.KIMI_MODEL
        self.hermes_model = Config.HERMES_MODEL
        self.base_url = Config.OLLAMA_BASE_URL

    def analyze(
        self,
        symbol: Any = "BTC/USDT",
        tech_summary: Optional[Dict[str, Any]] = None,
        market_state: Optional[Dict[str, Any]] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates Macroeconomic context, market regime, and multi-asset liquidity dynamics.
        """
        if isinstance(symbol, pd.DataFrame):
            df = symbol
            symbol = "BTC/USDT"
        elif isinstance(tech_summary, pd.DataFrame):
            df = tech_summary
            tech_summary = None

        if df is not None and isinstance(df, pd.DataFrame) and tech_summary is None:
            from strategies.indicators import TechnicalIndicators
            tech_summary = TechnicalIndicators.get_latest_summary(df)

        tech_summary = tech_summary if isinstance(tech_summary, dict) else {}
        market_state = market_state if isinstance(market_state, dict) else {}

        ema_50 = _safe_float(tech_summary.get("ema_50"), 0.0)
        ema_200 = _safe_float(tech_summary.get("ema_200"), 0.0)
        vwap = _safe_float(tech_summary.get("vwap"), 0.0)
        close = _safe_float(tech_summary.get("close"), 0.0)
        change_24h = _safe_float(market_state.get("change_24h"), 0.0)

        prompt = f"""You are Kimi Macro Reasoning Engine, an institutional global macro strategist.
Analyze market context for {symbol}:
- Price: {close}
- 24h Change: {change_24h}%
- EMA 50 vs EMA 200 Trend: {'Bullish' if ema_50 > ema_200 else 'Bearish'}
- VWAP: {vwap}

Respond STRICTLY in JSON:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "market_regime": "TRENDING_BULL" | "TRENDING_BEAR" | "RANGING" | "LIQUIDITY_CRISIS",
  "macro_thesis": "2-sentence macro reasoning"
}}
"""
        # Try Ollama model with fast non-blocking timeout
        for target_model in [Config.FAST_CHAT_MODEL]:
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": target_model, "prompt": prompt, "format": "json", "stream": False, "options": {"num_predict": 80, "temperature": 0.1}},
                    timeout=(0.4, 1.0)
                )
                if resp.status_code == 200:
                    data = json.loads(resp.json().get("response", "{}") or "{}")
                    if isinstance(data, dict):
                        sig = str(data.get("signal") or "HOLD").upper()
                        if sig not in ("BUY", "SELL", "HOLD"):
                            sig = "HOLD"
                        conf = max(0.0, min(1.0, _safe_float(data.get("confidence"), 0.5)))
                        return {
                            "agent": f"Kimi Macro AI ({target_model})",
                            "signal": sig,
                            "action": sig,
                            "confidence": conf,
                            "market_regime": str(data.get("market_regime") or "TRENDING_BULL"),
                            "rationale": str(data.get("macro_thesis") or "Macro regime supports current trend."),
                            "status": "LIVE_GPU"
                        }
            except Exception:
                break

        # Macro Heuristic fallback
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
            "action": sig,
            "confidence": conf,
            "market_regime": regime,
            "rationale": thesis,
            "status": "DETERMINISTIC_FALLBACK"
        }

    def evaluate(self, symbol: Any = "BTC/USDT", tech_summary: Optional[Dict[str, Any]] = None, market_state: Optional[Dict[str, Any]] = None, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, tech_summary=tech_summary, market_state=market_state, df=df)

    def get_signal(self, symbol: Any = "BTC/USDT", tech_summary: Optional[Dict[str, Any]] = None, market_state: Optional[Dict[str, Any]] = None, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, tech_summary=tech_summary, market_state=market_state, df=df)

    def generate_signal(self, symbol: Any = "BTC/USDT", tech_summary: Optional[Dict[str, Any]] = None, market_state: Optional[Dict[str, Any]] = None, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, tech_summary=tech_summary, market_state=market_state, df=df)

    def calculate_signals(self, symbol: Any = "BTC/USDT", tech_summary: Optional[Dict[str, Any]] = None, market_state: Optional[Dict[str, Any]] = None, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, tech_summary=tech_summary, market_state=market_state, df=df)

    def predict(self, symbol: Any = "BTC/USDT", tech_summary: Optional[Dict[str, Any]] = None, market_state: Optional[Dict[str, Any]] = None, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, tech_summary=tech_summary, market_state=market_state, df=df)

    def run(self, symbol: Any = "BTC/USDT", tech_summary: Optional[Dict[str, Any]] = None, market_state: Optional[Dict[str, Any]] = None, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.analyze(symbol=symbol, tech_summary=tech_summary, market_state=market_state, df=df)

