import json
import logging
import requests
from typing import Dict, Any
from config.settings import Config

logger = logging.getLogger("OmniTrade.QwenTechnicalAgent")

class QwenTechnicalAgent:
    def __init__(self):
        self.model = Config.QWEN_MODEL
        self.base_url = Config.OLLAMA_BASE_URL

    def analyze(self, symbol: str, tech_summary: Dict[str, Any], smc_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes Qwen 2.5 Coder 32B for deep multi-indicator and chart pattern analysis.
        """
        prompt = f"""You are Qwen 32B Technical Analysis Engine, a world-class institutional algorithmic trader.
Analyze the following live technical and Smart Money Concept (SMC) data for {symbol}:

Technical Indicators:
- Current Price: {tech_summary.get('close')}
- EMAs: EMA9={tech_summary.get('ema_9')}, EMA20={tech_summary.get('ema_20')}, EMA50={tech_summary.get('ema_50')}, EMA200={tech_summary.get('ema_200')}
- Golden Cross: {tech_summary.get('is_golden_cross')}, Death Cross: {tech_summary.get('is_death_cross')}
- RSI (14): {tech_summary.get('rsi')}
- MACD: {tech_summary.get('macd')}, Signal: {tech_summary.get('macd_signal')}, Hist: {tech_summary.get('macd_hist')}
- Bollinger Bands: Upper={tech_summary.get('bb_upper')}, Lower={tech_summary.get('bb_lower')}, %B={tech_summary.get('bb_pct')}
- SuperTrend: {'BULLISH' if tech_summary.get('supertrend_is_bull') else 'BEARISH'}
- VWAP: {tech_summary.get('vwap')}
- ATR (Volatility): {tech_summary.get('atr')}

Smart Money Concepts (SMC):
- Market Structure: {smc_summary.get('market_structure')}
- Liquidity Sweep: {smc_summary.get('liquidity_sweep')}
- Bullish FVG Present: {smc_summary.get('bullish_fvg_present')}
- Bearish FVG Present: {smc_summary.get('bearish_fvg_present')}
- Key Swing High: {smc_summary.get('recent_swing_high')}, Swing Low: {smc_summary.get('recent_swing_low')}

Respond STRICTLY in valid JSON matching this schema:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "chart_pattern": "short pattern name (e.g. Bullish Engulfing, FVG Retest, EMA Breakout)",
  "technical_rationale": "concise 2-sentence technical rationale",
  "recommended_entry": float,
  "stop_loss": float,
  "take_profit": float
}}
"""
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "options": {"num_predict": 90, "temperature": 0.1}
                },
                timeout=3.5
            )
            if resp.status_code == 200:
                data = json.loads(resp.json().get("response", "{}"))
                return {
                    "agent": "Qwen 2.5 Coder 32B",
                    "signal": data.get("signal", "HOLD").upper(),
                    "confidence": float(data.get("confidence", 0.5)),
                    "chart_pattern": data.get("chart_pattern", "Technical Pattern"),
                    "rationale": data.get("technical_rationale", "Analyzing indicators"),
                    "status": "LIVE_GPU"
                }
        except Exception as e:
            logger.debug(f"Ollama Qwen call error/timeout: {e}. Using deterministic quantitative heuristic fallback.")

        # Deterministic high-speed rule fallback
        rsi = tech_summary.get("rsi", 50)
        macd_hist = tech_summary.get("macd_hist", 0)
        super_bull = tech_summary.get("supertrend_is_bull", False)
        fvg_bull = smc_summary.get("bullish_fvg_present", False)
        fvg_bear = smc_summary.get("bearish_fvg_present", False)

        if super_bull and macd_hist > 0 and (rsi < 68 or fvg_bull):
            sig = "BUY"
            conf = 0.82 if fvg_bull else 0.72
            pat = "Bullish Momentum & SuperTrend Trend-Follow"
            rat = f"Price trading above SuperTrend with positive MACD histogram ({macd_hist}) and healthy RSI ({rsi})."
        elif not super_bull and macd_hist < 0 and (rsi > 32 or fvg_bear):
            sig = "SELL"
            conf = 0.80 if fvg_bear else 0.70
            pat = "Bearish Breakdown & FVG Liquidity Expansion"
            rat = f"Price below SuperTrend with bearish MACD divergence ({macd_hist}) and declining momentum."
        else:
            sig = "HOLD"
            conf = 0.50
            pat = "Consolidation / Range-bound"
            rat = "No strong multi-indicator directional edge identified."

        return {
            "agent": "Qwen 2.5 Coder 32B (Rule/Heuristic Mode)",
            "signal": sig,
            "confidence": conf,
            "chart_pattern": pat,
            "rationale": rat,
            "status": "DETERMINISTIC_FALLBACK"
        }
