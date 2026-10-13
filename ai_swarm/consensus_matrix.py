import logging
import math
import pandas as pd
from typing import Dict, Any, List, Optional
from config.settings import Config
from ai_swarm.qwen_technical_agent import QwenTechnicalAgent
from ai_swarm.deepseek_quant_agent import DeepSeekQuantAgent
from ai_swarm.kimi_macro_agent import KimiMacroAgent
from ai_swarm.hf_sentiment_agent import HFSentimentAgent
from ai_swarm.meta_learning_optimizer import MetaLearningOptimizer

logger = logging.getLogger("OmniTrade.AIConsensusMatrix")


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or isinstance(val, (dict, list, bool)):
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return default


class AIConsensusMatrix:
    def __init__(self, meta_optimizer: Optional[MetaLearningOptimizer] = None):
        self.qwen_agent = QwenTechnicalAgent()
        self.deepseek_agent = DeepSeekQuantAgent()
        self.kimi_agent = KimiMacroAgent()
        self.hf_agent = HFSentimentAgent()
        self.meta_optimizer = meta_optimizer or MetaLearningOptimizer()
        self.threshold = self.meta_optimizer.hyperparameters.get("min_consensus_threshold", Config.AI_CONSENSUS_THRESHOLD)

    def evaluate_market_consensus(
        self,
        symbol: Any = "BTC/USDT",
        tech_summary: Optional[Dict[str, Any]] = None,
        smc_summary: Optional[Dict[str, Any]] = None,
        ml_summary: Optional[Dict[str, Any]] = None,
        market_state: Optional[Dict[str, Any]] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Runs all AI agents in parallel/swarm and calculates weighted voting consensus using
        self-improving Meta-Learning dynamic Bayesian weights.
        """
        if isinstance(symbol, pd.DataFrame):
            df = symbol
            symbol = "BTC/USDT"
        elif isinstance(tech_summary, pd.DataFrame):
            df = tech_summary
            tech_summary = None

        if df is not None and isinstance(df, pd.DataFrame):
            if tech_summary is None:
                from strategies.indicators import TechnicalIndicators
                tech_summary = TechnicalIndicators.get_latest_summary(df)
            if smc_summary is None:
                from strategies.smart_money_concepts import SmartMoneyConcepts
                smc_summary = SmartMoneyConcepts.get_smc_summary(df)
            if ml_summary is None:
                from strategies.ml_predictor import MLAlphaPredictor
                ml_summary = MLAlphaPredictor().predict_next_candle(df)

        tech_summary = tech_summary if isinstance(tech_summary, dict) else {"rsi": 52.0, "macd_hist": 0.0, "supertrend_is_bull": True}
        smc_summary = smc_summary if isinstance(smc_summary, dict) else {"market_structure": "RANGING"}
        ml_summary = ml_summary if isinstance(ml_summary, dict) else {"prediction": "NEUTRAL", "confidence": 0.55}
        market_state = market_state if isinstance(market_state, dict) else {}

        price_change = _safe_float(market_state.get("change_24h"), 0.0)

        # Execute agent deliberations concurrently in parallel
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_qwen = pool.submit(self.qwen_agent.analyze, str(symbol), tech_summary, smc_summary, df)
            f_ds = pool.submit(self.deepseek_agent.analyze, str(symbol), tech_summary, ml_summary, df, smc_summary)
            f_kimi = pool.submit(self.kimi_agent.analyze, str(symbol), tech_summary, market_state, df)
            f_hf = pool.submit(self.hf_agent.analyze, str(symbol), price_change)
            qwen_out = f_qwen.result()
            deepseek_out = f_ds.result()
            kimi_out = f_kimi.result()
            hf_out = f_hf.result()

        agents = [qwen_out, deepseek_out, kimi_out, hf_out]

        # Pull adaptive weights from the MetaLearningOptimizer
        w = self.meta_optimizer.weights
        total_sub_w = (
            _safe_float(w.get("qwen_32b"), 0.35)
            + _safe_float(w.get("deepseek_r1"), 0.30)
            + _safe_float(w.get("kimi_macro"), 0.20)
            + _safe_float(w.get("llama_sentiment"), 0.15)
        )
        if total_sub_w <= 0:
            total_sub_w = 1.0
        weights = [
            _safe_float(w.get("qwen_32b"), 0.35) / total_sub_w,
            _safe_float(w.get("deepseek_r1"), 0.30) / total_sub_w,
            _safe_float(w.get("kimi_macro"), 0.20) / total_sub_w,
            _safe_float(w.get("llama_sentiment"), 0.15) / total_sub_w
        ]

        self.threshold = _safe_float(self.meta_optimizer.hyperparameters.get("min_consensus_threshold"), 0.68)

        # Calculate scores: BUY = +1, SELL = -1, HOLD = 0
        directional_score = 0.0
        total_confidence = 0.0

        for agent, weight in zip(agents, weights):
            sig = str(agent.get("signal") or "HOLD").upper()
            conf = _safe_float(agent.get("confidence"), 0.5)
            total_confidence += conf * weight

            if sig in ["BUY", "STRONG_BUY"]:
                directional_score += 1.0 * weight * conf
            elif sig in ["SELL", "STRONG_SELL"]:
                directional_score -= 1.0 * weight * conf

        # Final signal classification
        if directional_score >= 0.55 and total_confidence >= self.threshold:
            final_signal = "STRONG_BUY"
        elif directional_score >= 0.25:
            final_signal = "BUY"
        elif directional_score <= -0.55 and total_confidence >= self.threshold:
            final_signal = "STRONG_SELL"
        elif directional_score <= -0.25:
            final_signal = "SELL"
        else:
            final_signal = "HOLD"

        consensus_summary = {
            "symbol": str(symbol),
            "final_signal": final_signal,
            "signal": final_signal,
            "action": final_signal,
            "consensus_score": round(directional_score, 3),
            "score": round(directional_score, 3),
            "aggregate_confidence": round(total_confidence, 3),
            "confidence": round(total_confidence, 3),
            "threshold_met": total_confidence >= self.threshold,
            "adaptive_weights_applied": {
                "qwen_32b": round(weights[0], 3),
                "deepseek_r1": round(weights[1], 3),
                "kimi_macro": round(weights[2], 3),
                "llama_sentiment": round(weights[3], 3)
            },
            "meta_learning_iteration": self.meta_optimizer.iteration_count,
            "swarm_deliberation": agents,
            "summary_thesis": f"AI Swarm voted {final_signal} with {total_confidence*100:.1f}% confidence using Meta-Learning weights."
        }

        logger.info(f"Consensus for {symbol}: {final_signal} (Confidence: {total_confidence:.2f}, Score: {directional_score:+.2f})")
        return consensus_summary

    def get_consensus(self, symbol: Any = "BTC/USDT", df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Convenience method returning consensus evaluation for a symbol."""
        if isinstance(symbol, pd.DataFrame):
            df = symbol
            symbol = "BTC/USDT"
        if df is not None and isinstance(df, pd.DataFrame):
            return self.evaluate_market_consensus(symbol=symbol, df=df)
        tech_summary = {"rsi": 52.0, "macd": {"signal": "NEUTRAL"}, "trend": "BULLISH"}
        smc_summary = {"order_block": "BULLISH_OB", "fvg": "IMBALANCE_ABOVE"}
        ml_summary = {"predicted_return_1h": 0.008, "volatility_pred": 0.015}
        market_state = {"change_24h": 1.5, "funding_rate": 0.0001}
        return self.evaluate_market_consensus(symbol, tech_summary, smc_summary, ml_summary, market_state)

    def evaluate(
        self,
        symbol: Any = "BTC/USDT",
        tech_summary: Optional[Dict[str, Any]] = None,
        smc_summary: Optional[Dict[str, Any]] = None,
        ml_summary: Optional[Dict[str, Any]] = None,
        market_state: Optional[Dict[str, Any]] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        return self.evaluate_market_consensus(symbol, tech_summary, smc_summary, ml_summary, market_state, df=df)

    def generate_signal(self, symbol: Any = "BTC/USDT", df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.get_consensus(symbol=symbol, df=df)

    def calculate_signals(self, symbol: Any = "BTC/USDT", df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.get_consensus(symbol=symbol, df=df)

    def get_signal(self, symbol: Any = "BTC/USDT", df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.get_consensus(symbol=symbol, df=df)

    def predict(self, symbol: Any = "BTC/USDT", df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.get_consensus(symbol=symbol, df=df)

    def run(self, symbol: Any = "BTC/USDT", df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        return self.get_consensus(symbol=symbol, df=df)

