import logging
import pandas as pd
from typing import Dict, Any, List, Optional

from core.market_data import MarketDataProvider
from core.portfolio import Portfolio
from core.risk_engine import RiskEngine
from core.order_manager import OrderManager
from strategies.indicators import TechnicalIndicators
from strategies.smart_money_concepts import SmartMoneyConcepts
from strategies.ml_predictor import MLAlphaPredictor
from ai_swarm.consensus_matrix import AIConsensusMatrix

logger = logging.getLogger("OmniTrade.StrategyOrchestrator")

class StrategyOrchestrator:
    def __init__(
        self,
        market_data: MarketDataProvider,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        order_manager: OrderManager,
        consensus_matrix: AIConsensusMatrix
    ):
        self.market_data = market_data
        self.portfolio = portfolio
        self.risk_engine = risk_engine
        self.order_manager = order_manager
        self.consensus_matrix = consensus_matrix
        self.ml_predictor = MLAlphaPredictor()
        self.auto_trade_enabled = True
        self._analysis_cache: Dict[str, Any] = {} # (symbol, timeframe) -> (timestamp, data)

    def analyze_symbol(self, symbol: str, timeframe: str = "15m") -> Dict[str, Any]:
        """
        Runs the full analysis pipeline for a single asset:
        1. Fetch OHLCV data
        2. Compute Technical Indicators
        3. Compute Smart Money Concepts (SMC)
        4. Run Machine Learning Predictor
        5. Run Multi-Model AI Consensus Swarm
        """
        import time
        cache_key = f"{symbol}_{timeframe}"
        now_ts = time.time()
        if cache_key in self._analysis_cache:
            cached_ts, cached_data = self._analysis_cache[cache_key]
            if now_ts - cached_ts < 8.0: # 8-second cache
                return cached_data

        df = self.market_data.fetch_ohlcv(symbol, timeframe=timeframe, limit=120)
        ticker = self.market_data.get_current_ticker(symbol)

        tech_summary = TechnicalIndicators.get_latest_summary(df)
        smc_summary = SmartMoneyConcepts.get_smc_summary(df)
        ml_summary = self.ml_predictor.predict_next_candle(df)
        ai_consensus = self.consensus_matrix.evaluate_market_consensus(
            symbol=symbol,
            tech_summary=tech_summary,
            smc_summary=smc_summary,
            ml_summary=ml_summary,
            market_state=ticker
        )

        result = {
            "symbol": symbol,
            "ticker": ticker,
            "technical_indicators": tech_summary,
            "smart_money_concepts": smc_summary,
            "ml_prediction": ml_summary,
            "ai_consensus": ai_consensus,
            "ohlcv_candles": df.tail(60).to_dict(orient="records") if not df.empty else []
        }
        self._analysis_cache[cache_key] = (now_ts, result)
        return result

    def manage_open_positions(self, current_prices: Dict[str, float], atrs: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Institutional Stepped Trailing Stop-Loss, Break-Even Lock, and Multi-Tier Partial Take-Profit Execution.
        """
        from core.smart_exit_engine import SmartExitEngine
        closed_trades = []

        for symbol, pos in list(self.portfolio.positions.items()):
            price = current_prices.get(symbol, pos.get("entry_price", 0.0))
            atr = atrs.get(symbol, price * 0.012)
            
            exit_eval = SmartExitEngine.evaluate_position_exits(pos, price, atr)
            action = exit_eval.get("action")

            if action == "FULL_CLOSE":
                record = self.portfolio.close_position(symbol, price, exit_reason=exit_eval.get("reason", "SL_HIT"))
                if record:
                    closed_trades.append(record)
            elif action == "PARTIAL_CLOSE":
                close_pct = exit_eval.get("close_pct", 0.33)
                record = self.portfolio.partial_close_position(symbol, price, close_pct=close_pct, exit_reason=exit_eval.get("reason", "PARTIAL_TP"))
                if record:
                    closed_trades.append(record)
                pos["sl"] = exit_eval.get("new_sl", pos.get("sl"))
                pos["exit_stage"] = exit_eval.get("stage", 2)
                self.portfolio.save()
            elif action == "UPDATE_STOP_LOSS":
                pos["sl"] = exit_eval.get("new_sl", pos.get("sl"))
                pos["exit_stage"] = exit_eval.get("stage", 1)
                self.portfolio.save()

        return closed_trades

    def tick_cycle(self, symbols: List[str], timeframe: str = "15m") -> Dict[str, Any]:
        """
        Executes one full live scan across all watched symbols:
        1. Evaluates existing positions (Trailing stop, Stop Loss, Take Profit)
        2. Scans for new trade entries via AI Consensus
        3. Updates Portfolio values
        """
        current_prices = {}
        atrs = {}
        scanned_assets = []
        new_orders = []

        # 1. Gather live prices and analyze
        for symbol in symbols:
            try:
                analysis = self.analyze_symbol(symbol, timeframe=timeframe)
                current_price = analysis["ticker"].get("last", 0.0)
                atr = analysis["technical_indicators"].get("atr", current_price * 0.012)

                current_prices[symbol] = current_price
                atrs[symbol] = atr
                scanned_assets.append(analysis)

                # 2. Check if new order should be executed
                if self.auto_trade_enabled:
                    signal = analysis["ai_consensus"]["final_signal"]
                    conf = analysis["ai_consensus"]["aggregate_confidence"]

                    if signal in ["STRONG_BUY", "BUY", "STRONG_SELL", "SELL"] and conf >= 0.70:
                        reason = f"AI Swarm Consensus: {signal} ({conf*100:.1f}%) | SMC: {analysis['smart_money_concepts']['market_structure']}"
                        order_res = self.order_manager.execute_signal(
                            symbol=symbol,
                            signal=signal,
                            current_price=current_price,
                            atr=atr,
                            reason=reason
                        )
                        if order_res.get("status") in ["OPENED", "LIVE"]:
                            new_orders.append(order_res)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

        # 3. Update portfolio with latest prices and evaluate active positions
        self.portfolio.update_market_prices(current_prices)
        closed_trades = self.risk_engine.evaluate_active_positions(current_prices, atrs)

        return {
            "scanned_assets": scanned_assets,
            "new_orders": new_orders,
            "closed_trades": closed_trades,
            "portfolio_summary": self.portfolio.get_summary()
        }
