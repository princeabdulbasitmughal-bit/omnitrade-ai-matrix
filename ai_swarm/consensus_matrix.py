import logging
from typing import Dict, Any, List
from config.settings import Config
from ai_swarm.qwen_technical_agent import QwenTechnicalAgent
from ai_swarm.deepseek_quant_agent import DeepSeekQuantAgent
from ai_swarm.kimi_macro_agent import KimiMacroAgent
from ai_swarm.hf_sentiment_agent import HFSentimentAgent

from ai_swarm.meta_learning_optimizer import MetaLearningOptimizer

logger = logging.getLogger("OmniTrade.AIConsensusMatrix")

class AIConsensusMatrix:
    def __init__(self, meta_optimizer: MetaLearningOptimizer = None):
        self.qwen_agent = QwenTechnicalAgent()
        self.deepseek_agent = DeepSeekQuantAgent()
        self.kimi_agent = KimiMacroAgent()
        self.hf_agent = HFSentimentAgent()
        self.meta_optimizer = meta_optimizer or MetaLearningOptimizer()
        self.threshold = self.meta_optimizer.hyperparameters.get("min_consensus_threshold", Config.AI_CONSENSUS_THRESHOLD)

    def evaluate_market_consensus(
        self,
        symbol: str,
        tech_summary: Dict[str, Any],
        smc_summary: Dict[str, Any],
        ml_summary: Dict[str, Any],
        market_state: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Runs all AI agents in parallel/swarm and calculates weighted voting consensus using
        self-improving Meta-Learning dynamic Bayesian weights.
        """
        price_change = market_state.get("change_24h", 0.0) if market_state else 0.0

        # Execute agent deliberations
        qwen_out = self.qwen_agent.analyze(symbol, tech_summary, smc_summary)
        deepseek_out = self.deepseek_agent.analyze(symbol, tech_summary, ml_summary)
        kimi_out = self.kimi_agent.analyze(symbol, tech_summary, market_state)
        hf_out = self.hf_agent.analyze(symbol, price_change)

        agents = [qwen_out, deepseek_out, kimi_out, hf_out]
        
        # Pull adaptive weights from the MetaLearningOptimizer
        w = self.meta_optimizer.weights
        total_sub_w = w.get("qwen_32b", 0.35) + w.get("deepseek_r1", 0.30) + w.get("kimi_macro", 0.20) + w.get("llama_sentiment", 0.15)
        weights = [
            w.get("qwen_32b", 0.35) / total_sub_w,
            w.get("deepseek_r1", 0.30) / total_sub_w,
            w.get("kimi_macro", 0.20) / total_sub_w,
            w.get("llama_sentiment", 0.15) / total_sub_w
        ]
        
        self.threshold = self.meta_optimizer.hyperparameters.get("min_consensus_threshold", 0.68)

        # Calculate scores: BUY = +1, SELL = -1, HOLD = 0
        directional_score = 0.0
        total_confidence = 0.0

        for agent, weight in zip(agents, weights):
            sig = agent.get("signal", "HOLD")
            conf = agent.get("confidence", 0.5)
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
            "symbol": symbol,
            "final_signal": final_signal,
            "consensus_score": round(directional_score, 3),
            "aggregate_confidence": round(total_confidence, 3),
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
